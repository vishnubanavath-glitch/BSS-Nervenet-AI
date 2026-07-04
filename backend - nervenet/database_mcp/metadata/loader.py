import logging
import hashlib
import datetime
from typing import Dict, List, Any, Optional
from database_mcp.config import settings
from database_mcp.exceptions import MetadataError
from database_mcp.provider.mysql import execute_query
from database_mcp.metadata.cache import ColumnMetadata, TableMetadata, DatabaseMetadata, metadata_cache

logger = logging.getLogger(__name__)

def classify_domain(table_name: str) -> str:
    """Classify a table into a business domain based on its name."""
    tbl = table_name.lower()
    if any(x in tbl for x in ["bill", "invoice", "payment", "tariff", "revenue", "charge", "tax"]):
        return "Billing"
    if any(x in tbl for x in ["consumer", "user", "customer", "account", "profile", "client"]):
        return "Consumers"
    if any(x in tbl for x in ["meter", "reading", "consumption", "usage"]):
        return "Meters"
    if any(x in tbl for x in ["feeder", "dtr", "transformer", "substation", "grid", "line", "infra", "pole"]):
        return "Infrastructure"
    if any(x in tbl for x in ["energy", "power", "generation", "solar", "load", "kw", "kwh"]):
        return "Energy"
    if any(x in tbl for x in ["admin", "config", "setting", "log", "role", "permission", "audit"]):
        return "Administration"
    return "General"

def generate_aliases(table_name: str) -> List[str]:
    """Generate friendly aliases for a table name."""
    aliases = [table_name]
    # Replace underscores with spaces
    spaced = table_name.replace("_", " ")
    if spaced != table_name:
        aliases.append(spaced)
    # Singular/plural guesses
    if table_name.endswith("s") and len(table_name) > 1:
        aliases.append(table_name[:-1])
    else:
        aliases.append(table_name + "s")
    return list(set(aliases))

class MetadataLoader:
    """Handles loading of schema metadata from the MySQL INFORMATION_SCHEMA database, tracking schema changes and drift."""

    @classmethod
    def calculate_schema_hash(cls, tables_map: Dict[str, TableMetadata]) -> str:
        """Calculate a stable hash of the schema structures to detect changes."""
        lines = []
        for tbl_name in sorted(tables_map.keys()):
            tbl = tables_map[tbl_name]
            lines.append(f"Table: {tbl_name}")
            for col_name in sorted(tbl.columns.keys()):
                col = tbl.columns[col_name]
                lines.append(f"  Col: {col_name} {col.data_type} {col.is_nullable} {col.is_primary_key}")
        serialized = "\n".join(lines)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def load_and_cache(cls) -> DatabaseMetadata:
        """Query the database schema metadata, build relationship mappings, and populate the cache."""
        logger.info(f"Loading schema metadata for database '{settings.db_name}'...")
        
        try:
            # 1. Fetch all columns and basic table names
            columns_query = """
                SELECT 
                    TABLE_NAME, 
                    COLUMN_NAME, 
                    DATA_TYPE, 
                    IS_NULLABLE, 
                    COLUMN_KEY
                FROM 
                    INFORMATION_SCHEMA.COLUMNS
                WHERE 
                    TABLE_SCHEMA = %s
                ORDER BY 
                    TABLE_NAME, ORDINAL_POSITION;
            """
            cols_cols, cols_rows = await execute_query(columns_query, (settings.db_name,))
            
            tables_map: Dict[str, TableMetadata] = {}
            
            # Map columns to tables
            for row in cols_rows:
                table_name = row[0]
                column_name = row[1]
                data_type = row[2]
                is_nullable = (row[3] == "YES")
                is_primary_key = (row[4] == "PRI")
                
                if table_name not in tables_map:
                    tables_map[table_name] = TableMetadata(
                        name=table_name,
                        columns={},
                        primary_keys=[],
                        foreign_keys=[],
                        aliases=generate_aliases(table_name)
                    )
                
                col_meta = ColumnMetadata(
                    name=column_name,
                    data_type=data_type,
                    is_nullable=is_nullable,
                    is_primary_key=is_primary_key,
                    is_foreign_key=False,
                    foreign_key_target=None
                )
                tables_map[table_name].columns[column_name] = col_meta
                if is_primary_key:
                    tables_map[table_name].primary_keys.append(column_name)

            # 2. Fetch constraints, keys and foreign relationships
            keys_query = """
                SELECT 
                    TABLE_NAME, 
                    COLUMN_NAME, 
                    CONSTRAINT_NAME, 
                    REFERENCED_TABLE_NAME, 
                    REFERENCED_COLUMN_NAME
                FROM 
                    INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE 
                    TABLE_SCHEMA = %s
                    AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY 
                    TABLE_NAME, ORDINAL_POSITION;
            """
            keys_cols, keys_rows = await execute_query(keys_query, (settings.db_name,))
            
            relationships: List[Dict[str, Any]] = []
            
            for row in keys_rows:
                table_name = row[0]
                column_name = row[1]
                ref_table = row[3]
                ref_column = row[4]
                
                if table_name in tables_map and column_name in tables_map[table_name].columns:
                    tables_map[table_name].foreign_keys.append({
                        "column": column_name,
                        "referenced_table": ref_table,
                        "referenced_column": ref_column
                    })
                    
                    col_meta = tables_map[table_name].columns[column_name]
                    col_meta.is_foreign_key = True
                    col_meta.foreign_key_target = f"{ref_table}.{ref_column}"
                    
                    relationships.append({
                        "from_table": table_name,
                        "from_column": column_name,
                        "to_table": ref_table,
                        "to_column": ref_column
                    })

            # 3. Fetch table statistics (rows, size, comments/descriptions)
            tables_query = """
                SELECT 
                    TABLE_NAME,
                    TABLE_ROWS,
                    DATA_LENGTH,
                    INDEX_LENGTH,
                    UPDATE_TIME,
                    TABLE_COMMENT
                FROM 
                    INFORMATION_SCHEMA.TABLES
                WHERE 
                    TABLE_SCHEMA = %s;
            """
            try:
                tbls_cols, tbls_rows = await execute_query(tables_query, (settings.db_name,))
                for row in tbls_rows:
                    table_name = row[0]
                    if table_name in tables_map:
                        tbl_meta = tables_map[table_name]
                        tbl_meta.row_count = row[1] if row[1] is not None else 0
                        tbl_meta.data_length = row[2] if row[2] is not None else 0
                        tbl_meta.index_length = row[3] if row[3] is not None else 0
                        tbl_meta.update_time = str(row[4]) if row[4] is not None else None
                        
                        comment = row[5]
                        if comment:
                            tbl_meta.description = comment
                            # Exclude comment if empty or generic
                            if "InnoDB free" in comment:
                                tbl_meta.description = None
            except Exception as e:
                logger.warning(f"Could not load table storage metadata from INFORMATION_SCHEMA.TABLES: {e}")

            # 4. Logical business domains grouping
            business_domains: Dict[str, List[str]] = {}
            for table_name in tables_map:
                domain = classify_domain(table_name)
                if domain not in business_domains:
                    business_domains[domain] = []
                business_domains[domain].append(table_name)

            # Generate schema checksum and version
            schema_hash = cls.calculate_schema_hash(tables_map)
            now_str = datetime.datetime.now().isoformat()
            
            # Get existing metadata if any to preserve/increment version
            existing = metadata_cache.get()
            next_version = 1
            if existing:
                if existing.schema_version == schema_hash:
                    next_version = existing.metadata_version
                else:
                    next_version = existing.metadata_version + 1

            summary = f"Database '{settings.db_name}' contains {len(tables_map)} tables: {', '.join(tables_map.keys())}."
            
            db_meta = DatabaseMetadata(
                database_name=settings.db_name,
                tables=tables_map,
                relationships=relationships,
                summary=summary,
                metadata_version=next_version,
                schema_version=schema_hash,
                cache_timestamp=now_str,
                last_refresh=now_str,
                business_domains=business_domains
            )
            
            metadata_cache.set(db_meta)
            logger.info(f"Loaded schema metadata version {next_version} with {len(tables_map)} tables, "
                        f"{len(relationships)} relationships, mapped to {len(business_domains)} domains.")
            return db_meta
            
        except Exception as e:
            logger.error(f"Error loading database schema metadata: {e}", exc_info=True)
            raise MetadataError(f"Failed to load schema metadata from MySQL: {str(e)}") from e

    @classmethod
    async def check_drift_and_refresh(cls) -> Dict[str, Any]:
        """Check if schema has changed. If so, perform drift detection, reload cache, and log changes."""
        if not metadata_cache.is_warmed():
            meta = await cls.load_and_cache()
            return {"drift_detected": False, "metadata_version": meta.metadata_version}

        cached_meta = metadata_cache.get()
        now_str = datetime.datetime.now().isoformat()
        
        # Quick columns count/length check to detect if query hash changed
        checksum_query = """
            SELECT COUNT(*), SUM(LENGTH(COLUMN_NAME) + LENGTH(TABLE_NAME))
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s;
        """
        try:
            _, rows = await execute_query(checksum_query, (settings.db_name,))
            if not rows or not rows[0]:
                cached_meta.last_refresh = now_str
                return {"drift_detected": False, "metadata_version": cached_meta.metadata_version}
            
            col_count, col_sum = rows[0]
            col_sum = col_sum or 0
            checksum_str = f"{col_count}:{col_sum}"
            
            # Run load_and_cache but only log and increment version if the schema hash actually differs
            # This is robust because it queries columns and checks constraints
            temp_db_meta = await cls.load_and_cache()
            
            if temp_db_meta.schema_version != cached_meta.schema_version:
                # Drift detected! Detect specific changes
                drift_info = cls.detect_drift(cached_meta, temp_db_meta)
                logger.warning(f"SCHEMA DRIFT DETECTED: {drift_info}")
                
                # Increment metadata version
                temp_db_meta.metadata_version = cached_meta.metadata_version + 1
                metadata_cache.set(temp_db_meta)
                
                return {
                    "drift_detected": True,
                    "metadata_version": temp_db_meta.metadata_version,
                    "changes": drift_info
                }
            else:
                # Update last refresh timestamp on cached metadata
                cached_meta.last_refresh = now_str
                return {"drift_detected": False, "metadata_version": cached_meta.metadata_version}
                
        except Exception as e:
            logger.error(f"Error checking for schema drift: {e}", exc_info=True)
            # Safe fallback: don't break execution, return false
            return {"drift_detected": False, "metadata_version": cached_meta.metadata_version if cached_meta else 1}

    @classmethod
    def detect_drift(cls, old: DatabaseMetadata, new: DatabaseMetadata) -> Dict[str, Any]:
        """Compare two metadata sets and list new, renamed/removed tables, columns, and datatype changes."""
        changes = {
            "new_tables": [],
            "removed_tables": [],
            "new_columns": [],
            "removed_columns": [],
            "changed_datatypes": []
        }
        
        old_tables = set(old.tables.keys())
        new_tables = set(new.tables.keys())
        
        changes["new_tables"] = list(new_tables - old_tables)
        changes["removed_tables"] = list(old_tables - new_tables)
        
        common_tables = old_tables.intersection(new_tables)
        for tbl_name in common_tables:
            old_tbl = old.tables[tbl_name]
            new_tbl = new.tables[tbl_name]
            
            old_cols = set(old_tbl.columns.keys())
            new_cols = set(new_tbl.columns.keys())
            
            for c in (new_cols - old_cols):
                changes["new_columns"].append(f"{tbl_name}.{c}")
                
            for c in (old_cols - new_cols):
                changes["removed_columns"].append(f"{tbl_name}.{c}")
                
            for c in old_cols.intersection(new_cols):
                if old_tbl.columns[c].data_type != new_tbl.columns[c].data_type:
                    changes["changed_datatypes"].append({
                        "column": f"{tbl_name}.{c}",
                        "old_type": old_tbl.columns[c].data_type,
                        "new_type": new_tbl.columns[c].data_type
                    })
                    
        return {k: v for k, v in changes.items() if v}

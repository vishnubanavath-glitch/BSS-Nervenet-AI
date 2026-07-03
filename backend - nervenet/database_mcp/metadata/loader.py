import logging
from typing import Dict, List, Any
from database_mcp.config import settings
from database_mcp.exceptions import MetadataError
from database_mcp.provider.mysql import execute_query
from database_mcp.metadata.cache import ColumnMetadata, TableMetadata, DatabaseMetadata, metadata_cache

logger = logging.getLogger(__name__)

class MetadataLoader:
    """Handles loading of schema metadata from the MySQL INFORMATION_SCHEMA database."""

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
            
            if not cols_rows:
                logger.warning(f"No tables or columns found in database '{settings.db_name}'.")
                
            tables_map: Dict[str, TableMetadata] = {}
            
            # Helper to map columns
            for row in cols_rows:
                # columns: TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
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
                        foreign_keys=[]
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
                # columns: TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                table_name = row[0]
                column_name = row[1]
                ref_table = row[3]
                ref_column = row[4]
                
                # Verify that the table and columns exist in our mapping
                if table_name in tables_map and column_name in tables_map[table_name].columns:
                    tables_map[table_name].foreign_keys.append({
                        "column": column_name,
                        "referenced_table": ref_table,
                        "referenced_column": ref_column
                    })
                    
                    # Update column metadata
                    col_meta = tables_map[table_name].columns[column_name]
                    col_meta.is_foreign_key = True
                    col_meta.foreign_key_target = f"{ref_table}.{ref_column}"
                    
                    relationships.append({
                        "from_table": table_name,
                        "from_column": column_name,
                        "to_table": ref_table,
                        "to_column": ref_column
                    })

            # Create summary
            summary = f"Database '{settings.db_name}' contains {len(tables_map)} tables: {', '.join(tables_map.keys())}."
            
            db_meta = DatabaseMetadata(
                database_name=settings.db_name,
                tables=tables_map,
                relationships=relationships,
                summary=summary
            )
            
            # Save to global cache
            metadata_cache.set(db_meta)
            logger.info(f"Loaded schema metadata with {len(tables_map)} tables and {len(relationships)} relationships.")
            return db_meta
            
        except Exception as e:
            logger.error(f"Error loading database schema metadata: {e}", exc_info=True)
            raise MetadataError(f"Failed to load schema metadata from MySQL: {str(e)}") from e

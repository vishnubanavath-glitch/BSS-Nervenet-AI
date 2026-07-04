import time
import logging
from typing import Dict, Any, Optional, List
from database_mcp.config import settings
from database_mcp.provider.mysql import execute_query
from database_mcp.metadata.cache import metadata_cache

logger = logging.getLogger(__name__)

class TableProfileCache:
    """Simple in-memory cache for table profiles with TTL."""
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, table_name: str) -> Optional[Dict[str, Any]]:
        if table_name not in self._cache:
            return None
        cached = self._cache[table_name]
        if time.time() - cached["timestamp"] > settings.profiler_cache_ttl:
            del self._cache[table_name]
            return None
        return cached["profile"]

    def set(self, table_name: str, profile: Dict[str, Any]) -> None:
        self._cache[table_name] = {
            "timestamp": time.time(),
            "profile": profile
        }

    def clear(self) -> None:
        self._cache.clear()

profile_cache = TableProfileCache()

class DatabaseProfiler:
    """Service to compute lightweight profiles and statistics for database tables."""

    @classmethod
    async def profile_table(cls, table_name: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Compute or retrieve from cache a lightweight profile of a database table."""
        if not force_refresh:
            cached = profile_cache.get(table_name)
            if cached:
                logger.info(f"Profiler cache hit for table '{table_name}'")
                cached["cache_hit"] = True
                return cached

        logger.info(f"Computing profile for table '{table_name}'...")
        
        # 1. Verify table exists in metadata cache
        meta = metadata_cache.get()
        if not meta or table_name not in meta.tables:
            # Fallback check or return empty
            return {
                "success": False,
                "error": f"Table '{table_name}' not found in metadata cache."
            }

        tbl_meta = meta.tables[table_name]
        columns = tbl_meta.columns
        
        # Initialize profile structure
        profile = {
            "table_name": table_name,
            "row_count": tbl_meta.row_count,
            "approximate_size_bytes": tbl_meta.data_length + tbl_meta.index_length,
            "primary_keys": tbl_meta.primary_keys,
            "foreign_keys": tbl_meta.foreign_keys,
            "columns": [],
            "indexes": [],
            "date_range": None,
            "cache_hit": False
        }

        # 2. Fetch indexes
        indexes_query = """
            SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s;
        """
        try:
            _, index_rows = await execute_query(indexes_query, (settings.db_name, table_name))
            indexes_map = {}
            for row in index_rows:
                idx_name, col_name, non_unique = row[0], row[1], row[2]
                if idx_name not in indexes_map:
                    indexes_map[idx_name] = {
                        "name": idx_name,
                        "columns": [],
                        "unique": not non_unique
                    }
                indexes_map[idx_name]["columns"].append(col_name)
            profile["indexes"] = list(indexes_map.values())
        except Exception as e:
            logger.warning(f"Failed to query indexes for table '{table_name}': {e}")

        # 3. Perform a safe query to gather nulls, min/max dates, and distinct count estimation
        # Identify date/datetime columns
        date_cols = []
        for col_name, col in columns.items():
            if any(x in col.data_type.lower() for x in ["date", "time", "year"]):
                date_cols.append(col_name)

        # Build dynamic queries for null percentages and low-cardinality columns
        null_selects = []
        distinct_selects = []
        date_selects = []

        for col_name, col in columns.items():
            # Null check
            null_selects.append(f"SUM(CASE WHEN `{col_name}` IS NULL THEN 1 ELSE 0 END) AS `{col_name}_nulls`")
            
            # Distinct estimation: only do COUNT(DISTINCT) if table is reasonably small (< 100k rows) to avoid timeouts
            if tbl_meta.row_count < 100000:
                distinct_selects.append(f"COUNT(DISTINCT `{col_name}`) AS `{col_name}_distinct`")

        for d_col in date_cols:
            date_selects.append(f"MIN(`{d_col}`) AS `{d_col}_min`")
            date_selects.append(f"MAX(`{d_col}`) AS `{d_col}_max`")

        all_selects = ["COUNT(*) as `total_rows`"] + null_selects + distinct_selects + date_selects
        query = f"SELECT {', '.join(all_selects)} FROM `{table_name}`"

        try:
            # Inject a timeout safety specifically for profiling
            cols_list, rows_list = await execute_query(query, timeout=10.0)
            if rows_list:
                stats = dict(zip(cols_list, rows_list[0]))
                actual_rows = stats.get("total_rows", tbl_meta.row_count)
                profile["row_count"] = actual_rows

                # Update columns metadata
                for col_name, col in columns.items():
                    nulls = stats.get(f"{col_name}_nulls", 0)
                    null_pct = round((nulls / actual_rows * 100), 2) if actual_rows > 0 else 0.0
                    
                    col_info = {
                        "name": col_name,
                        "data_type": col.data_type,
                        "nullable": col.is_nullable,
                        "null_percentage": null_pct,
                        "is_primary": col.is_primary_key,
                        "is_foreign": col.is_foreign_key
                    }
                    
                    distinct_val = stats.get(f"{col_name}_distinct")
                    if distinct_val is not None:
                        col_info["distinct_count"] = distinct_val
                        
                    profile["columns"].append(col_info)

                # Set date ranges if any date columns existed
                ranges = {}
                for d_col in date_cols:
                    min_val = stats.get(f"{d_col}_min")
                    max_val = stats.get(f"{d_col}_max")
                    if min_val is not None or max_val is not None:
                        ranges[d_col] = {
                            "min": str(min_val) if min_val else None,
                            "max": str(max_val) if max_val else None
                        }
                if ranges:
                    profile["date_range"] = ranges
            else:
                cls._fill_fallback_columns(profile, columns)
        except Exception as e:
            logger.warning(f"Lightweight dynamic profiling query failed for table '{table_name}': {e}. Using fallback schema profile.")
            cls._fill_fallback_columns(profile, columns)

        # Cache results
        profile_cache.set(table_name, profile)
        return profile

    @classmethod
    def _fill_fallback_columns(cls, profile: Dict[str, Any], columns: Dict[str, Any]) -> None:
        """Fill basic column info without querying table rows when query fails/timeouts."""
        for col_name, col in columns.items():
            profile["columns"].append({
                "name": col_name,
                "data_type": col.data_type,
                "nullable": col.is_nullable,
                "null_percentage": 0.0,
                "is_primary": col.is_primary_key,
                "is_foreign": col.is_foreign_key
            })

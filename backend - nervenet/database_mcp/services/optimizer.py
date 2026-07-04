import re
import logging
import sqlparse
from database_mcp.config import settings
from database_mcp.metadata.cache import metadata_cache

logger = logging.getLogger(__name__)

class SQLOptimizer:
    """Service to automatically optimize SQL queries prior to execution without changing semantics."""

    @classmethod
    def optimize(cls, sql: str) -> str:
        """Apply safe optimization rules (limit injection, wildcard expansion) to SELECT queries."""
        sql_stripped = sql.strip()
        if not sql_stripped:
            return sql

        try:
            parsed = sqlparse.parse(sql_stripped)
            if not parsed:
                return sql
            
            stmt = parsed[0]
            if stmt.get_type() != "SELECT":
                return sql
        except Exception as e:
            logger.warning(f"Failed to parse SQL for optimization: {e}. Skipping optimization.")
            return sql

        optimized_sql = sql_stripped

        # 1. Expand SELECT * to explicit columns if cache is warmed
        meta = metadata_cache.get()
        if meta:
            # Matches SELECT * FROM table_name
            single_table_match = re.search(
                r'\bSELECT\s+\*\s+FROM\s+`?([a-zA-Z0-9_]+)`?', 
                optimized_sql, 
                re.IGNORECASE
            )
            if single_table_match:
                table_name = single_table_match.group(1)
                if table_name in meta.tables:
                    columns = list(meta.tables[table_name].columns.keys())
                    col_list_str = ", ".join(f"`{table_name}`.`{c}`" for c in columns)
                    # Replace the first * (which is select wildcard) with explicit columns
                    optimized_sql = re.sub(r'\*', col_list_str, optimized_sql, count=1)
                    logger.info(f"Expanded SELECT * for table '{table_name}' to explicit columns.")

        # 2. Inject LIMIT if missing and auto-limit is enabled
        if settings.enable_auto_limit:
            # Check if query already has a LIMIT clause (case-insensitive)
            # Find LIMIT keyword in flattened tokens to prevent false matches inside strings/comments
            has_limit = False
            try:
                for token in stmt.flatten():
                    if token.value.upper() == "LIMIT":
                        has_limit = True
                        break
            except Exception:
                has_limit = "LIMIT" in optimized_sql.upper()

            if not has_limit:
                # Remove trailing semicolon for clean append
                ended_with_semicolon = optimized_sql.endswith(";")
                clean_sql = optimized_sql.rstrip(";")
                optimized_sql = f"{clean_sql} LIMIT {settings.max_rows_returned}"
                if ended_with_semicolon:
                    optimized_sql += ";"
                logger.info(f"Injected auto-limit of {settings.max_rows_returned} rows.")

        return optimized_sql

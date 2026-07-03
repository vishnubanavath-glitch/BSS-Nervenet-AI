import time
import logging
from typing import Optional, Dict, Any
from database_mcp.sql.validator import SQLValidator
from database_mcp.provider.mysql import execute_query
from database_mcp.config import settings

logger = logging.getLogger(__name__)

class SQLExecutor:
    """Orchestrates query validation, execution, row limiting, and response formatting."""

    @classmethod
    async def execute(
        cls,
        sql: str,
        timeout: Optional[float] = None,
        max_rows: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate and execute a SQL statement.
        
        Args:
            sql: The SQL query string to run.
            timeout: Optional override for query execution timeout.
            max_rows: Optional override for maximum rows returned.
            
        Returns:
            A structured dict containing columns, rows, row count, and execution time.
        """
        # 1. Validate query safety
        SQLValidator.validate(sql)

        # 2. Determine limits
        limit = max_rows if max_rows is not None else settings.max_rows_returned
        
        # 3. Execute and measure time
        logger.info(f"Executing SQL query (limit={limit}): {sql}")
        start_time = time.perf_counter()
        
        columns, rows = await execute_query(
            query=sql,
            timeout=timeout,
            limit=limit
        )
        
        end_time = time.perf_counter()
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        
        logger.info(f"Query completed in {execution_time_ms}ms, returned {len(rows)} rows.")

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms
        }

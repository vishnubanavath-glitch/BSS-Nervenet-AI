import time
import logging
from typing import Optional, Dict, Any
from database_mcp.sql.validator import SQLValidator
from database_mcp.provider.mysql import execute_query
from database_mcp.config import settings
from database_mcp.exceptions import QueryPlanningError, SqlExecutionError
from database_mcp.services.optimizer import SQLOptimizer
from database_mcp.services.metrics import MetricsService

logger = logging.getLogger(__name__)

class SQLExecutor:
    """Orchestrates query validation, optimization, cost estimation, execution, and response formatting."""

    @classmethod
    async def execute(
        cls,
        sql: str,
        timeout: Optional[float] = None,
        max_rows: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate, optimize, estimate cost, and execute a SQL statement.
        
        Args:
            sql: The SQL query string to run.
            timeout: Optional override for query execution timeout.
            max_rows: Optional override for maximum rows returned.
            
        Returns:
            A structured dict containing columns, rows, row count, and execution time.
        """
        # 1. Validate query safety
        SQLValidator.validate(sql)

        # 2. Optimize the query (auto limit, expand *)
        optimized_sql = SQLOptimizer.optimize(sql)
        logger.info(f"Optimized SQL: {optimized_sql}")

        # 3. Estimate Query Cost using EXPLAIN
        await cls.estimate_cost(optimized_sql)

        # 4. Determine limits
        limit = max_rows if max_rows is not None else settings.max_rows_returned
        
        # 5. Execute and measure time
        logger.info(f"Executing SQL query (limit={limit}): {optimized_sql}")
        start_time = time.perf_counter()
        
        columns, rows = await execute_query(
            query=optimized_sql,
            timeout=timeout,
            limit=limit
        )
        
        end_time = time.perf_counter()
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        
        logger.info(f"Query completed in {execution_time_ms}ms, returned {len(rows)} rows.")
        MetricsService.record_sql_execution(execution_time_ms)

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms
        }

    @classmethod
    async def estimate_cost(cls, sql: str) -> None:
        """Analyze query plan via EXPLAIN and reject if cost exceeds thresholds."""
        if settings.query_cost_limit <= 0.0:
            return
        explain_sql = f"EXPLAIN {sql}"
        try:
            cols, rows = await execute_query(explain_sql, timeout=5.0)
            
            total_estimated_rows = 1
            join_count = 0
            has_full_table_scan = False
            
            # Map columns to lowercase to find indexes
            col_map = {c.lower(): idx for idx, c in enumerate(cols)}
            
            rows_idx = col_map.get("rows")
            type_idx = col_map.get("type")
            
            for r in rows:
                join_count += 1
                
                # Rows to scan
                step_rows = 1
                if rows_idx is not None and r[rows_idx] is not None:
                    try:
                        step_rows = int(r[rows_idx])
                    except (ValueError, TypeError):
                        step_rows = 1
                total_estimated_rows *= max(step_rows, 1)
                
                # Check for full table scan
                if type_idx is not None and r[type_idx] is not None:
                    if str(r[type_idx]).upper() == "ALL":
                        has_full_table_scan = True
                        
            # Enforce join limits
            if join_count > settings.max_joins_allowed:
                raise QueryPlanningError(
                    f"Query exceeds maximum joins limit ({join_count} > {settings.max_joins_allowed})."
                )
                
            # Enforce row scanning limits
            cost_threshold = settings.query_cost_limit
            if total_estimated_rows > cost_threshold:
                raise QueryPlanningError(
                    f"Query estimated cost ({total_estimated_rows} rows to scan) exceeds the threshold ({cost_threshold})."
                )
                
            # Enforce large full table scan limit
            if has_full_table_scan and total_estimated_rows > 10000:
                raise QueryPlanningError(
                    f"Forbidden full table scan detected on a large table ({total_estimated_rows} rows to scan). "
                    "Please filter by indexed columns."
                )
                
        except QueryPlanningError as qe:
            logger.warning(f"Cost estimation rejected query: {qe.message}")
            raise qe
        except Exception as e:
            # Do not block queries if EXPLAIN fails due to unsupported EXPLAIN syntax (e.g. DESCRIBE or SHOW queries)
            logger.debug(f"EXPLAIN cost estimation skipped or failed: {e}")

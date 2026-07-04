import time
import logging
import collections
from typing import Optional, Dict, Any
from database_mcp.sql.validator import SQLValidator
from database_mcp.provider.mysql import execute_query
from database_mcp.config import settings
from database_mcp.exceptions import QueryPlanningError, SqlExecutionError
from database_mcp.services.optimizer import SQLOptimizer
from database_mcp.services.metrics import MetricsService
from database_mcp.sql.analytics import (
    determine_sampling_method,
    strip_outer_limit,
    detect_column_types,
    compute_python_stats,
    build_sql_stats_query,
    build_sql_duplicate_query,
    merge_stats,
    count_joins_in_sql,
    get_simple_table_name_if_no_filters
)

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
        """Validate, optimize, estimate cost, and execute a SQL statement with analytics summaries.
        
        Args:
            sql: The SQL query string to run.
            timeout: Optional override for query execution timeout.
            max_rows: Optional override for maximum rows returned.
            
        Returns:
            A structured dict containing columns, rows, row count, execution times, and metadata.
        """
        start_time = time.perf_counter()
        
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
        db_start = time.perf_counter()
        
        columns, rows = await execute_query(
            query=optimized_sql,
            timeout=timeout,
            limit=limit
        )
        
        db_end = time.perf_counter()
        database_time_ms = (db_end - db_start) * 1000
        
        row_count = len(rows)
        logger.info(f"Query completed in {database_time_ms:.2f}ms, returned {row_count} rows.")

        # Check if query is SELECT or WITH
        is_query_eligible = False
        try:
            import sqlparse
            parsed = sqlparse.parse(sql)
            if parsed:
                stmt_type = parsed[0].get_type()
                if stmt_type == "SELECT":
                    is_query_eligible = True
                else:
                    first_token = parsed[0].token_first()
                    if first_token and first_token.value.upper() == "WITH":
                        is_query_eligible = True
        except Exception:
            cleaned = sql.strip().upper()
            is_query_eligible = cleaned.startswith("SELECT") or cleaned.startswith("WITH")

        total_matching_rows = row_count
        truncated = False
        limit_used = limit
        remaining_rows = 0
        coverage_percent = 100.0
        can_fetch_more = False

        if is_query_eligible and row_count == limit:
            # Check if this is a simple query on a single table without filters/joins
            simple_table = get_simple_table_name_if_no_filters(optimized_sql)
            use_meta = False
            
            if simple_table:
                from database_mcp.metadata.cache import metadata_cache
                meta = metadata_cache.get()
                if meta:
                    tbl_meta = None
                    for t_name, t_m in meta.tables.items():
                        if t_name.lower() == simple_table:
                            tbl_meta = t_m
                            break
                    if tbl_meta and tbl_meta.row_count is not None:
                        total_matching_rows = tbl_meta.row_count
                        logger.info(f"Using metadata cache row count for simple table query on '{simple_table}': {total_matching_rows}")
                        use_meta = True

            if not use_meta:
                # Run count query to see if there are more matching rows
                sql_without_limit = strip_outer_limit(optimized_sql)
                count_sql = f"SELECT COUNT(*) AS total_matching_rows FROM ({sql_without_limit}) AS sub_count"
                logger.info(f"Running count query to determine truncation: {count_sql}")
                
                db_count_start = time.perf_counter()
                try:
                    count_cols, count_rows = await execute_query(count_sql, timeout=timeout)
                    if count_rows and count_rows[0]:
                        total_matching_rows = int(count_rows[0][0])
                except Exception as e:
                    logger.warning(f"Failed to execute count query: {e}. Defaulting total_matching_rows to limit.")
                    total_matching_rows = row_count
                db_count_end = time.perf_counter()
                database_time_ms += (db_count_end - db_count_start) * 1000
            
            if total_matching_rows > limit:
                truncated = True
                remaining_rows = total_matching_rows - row_count
                coverage_percent = (row_count / total_matching_rows * 100)
                can_fetch_more = True

        should_compute_stats = is_query_eligible and (total_matching_rows > 100)
        stats_data = {}
        dq_data = {}
        statistics_time_ms = 0.0

        if should_compute_stats:
            stats_start = time.perf_counter()
            col_types = detect_column_types(columns, rows)
            
            if not truncated:
                # Calculate in Python
                py_stats = compute_python_stats(columns, rows, col_types)
                stats_data = py_stats["stats"]
                dq_cols = py_stats["data_quality_cols"]
                
                try:
                    def make_hashable(val):
                        if isinstance(val, (list, dict, set)):
                            return str(val)
                        return val
                    unique_rows = len(set(tuple(make_hashable(x) for x in r) for r in rows))
                    duplicate_rows = row_count - unique_rows
                except Exception:
                    duplicate_rows = None
                    
                dq_data = {
                    "duplicate_rows": duplicate_rows,
                    "columns": dq_cols
                }
                stats_end = time.perf_counter()
                statistics_time_ms = (stats_end - stats_start) * 1000
            else:
                # Calculate using Database + Python sample merging
                # 1. Run stats query on DB
                sql_without_limit = strip_outer_limit(optimized_sql)
                stats_sql = build_sql_stats_query(sql_without_limit, columns, col_types)
                logger.info(f"Running database-side statistics query: {stats_sql}")
                
                db_stats_start = time.perf_counter()
                db_stats_row = {}
                try:
                    stats_cols, stats_rows = await execute_query(stats_sql, timeout=timeout)
                    if stats_rows and stats_rows[0]:
                        db_stats_row = dict(zip(stats_cols, stats_rows[0]))
                except Exception as e:
                    logger.warning(f"Database-side statistics query failed: {e}")
                db_stats_end = time.perf_counter()
                database_time_ms += (db_stats_end - db_stats_start) * 1000
                
                # 2. Run duplicate rows query on DB
                dup_sql = build_sql_duplicate_query(sql_without_limit, columns)
                logger.info(f"Running database-side duplicate rows query: {dup_sql}")
                
                db_dup_start = time.perf_counter()
                duplicate_rows = None
                try:
                    dup_cols, dup_rows = await execute_query(dup_sql, timeout=timeout)
                    if dup_rows and dup_rows[0] and dup_rows[0][0] is not None:
                        duplicate_rows = int(dup_rows[0][0])
                except Exception as e:
                    logger.warning(f"Database-side duplicate query failed: {e}. Falling back to sample.")
                    try:
                        def make_hashable(val):
                            if isinstance(val, (list, dict, set)):
                                return str(val)
                            return val
                        unique_rows = len(set(tuple(make_hashable(x) for x in r) for r in rows))
                        duplicate_rows = row_count - unique_rows
                    except Exception:
                        duplicate_rows = None
                db_dup_end = time.perf_counter()
                database_time_ms += (db_dup_end - db_dup_start) * 1000
                
                # 3. Compute Python sample stats and merge
                py_sample_stats = compute_python_stats(columns, rows, col_types)
                merged = merge_stats(db_stats_row, py_sample_stats, columns, col_types, total_matching_rows)
                
                stats_data = merged["stats"]
                dq_cols = merged["data_quality_cols"]
                dq_data = {
                    "duplicate_rows": duplicate_rows,
                    "columns": dq_cols
                }
                stats_end = time.perf_counter()
                # Subtract database time from python time measurement
                statistics_time_ms = (stats_end - stats_start) * 1000 - ((db_stats_end - db_stats_start) * 1000 + (db_dup_end - db_dup_start) * 1000)
                statistics_time_ms = max(statistics_time_ms, 0.0)

        formatting_start = time.perf_counter()
        
        # Build execution block
        execution_meta = {
            "database_time_ms": round(database_time_ms, 2),
            "statistics_time_ms": round(statistics_time_ms, 2)
        }
        if is_query_eligible:
            execution_meta.update({
                "total_matching_rows": total_matching_rows,
                "returned_rows": row_count,
                "limit_used": limit_used,
                "truncated": truncated,
                "remaining_rows": remaining_rows,
                "coverage_percent": round(coverage_percent, 2),
                "can_fetch_more": can_fetch_more
            })

        res = {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": row_count
        }

        if is_query_eligible:
            res["execution"] = execution_meta
            res["sample"] = {
                "sampling_method": determine_sampling_method(optimized_sql)
            }
            if should_compute_stats:
                res["statistical_summary"] = stats_data
                res["data_quality"] = dq_data
            if truncated:
                res["analysis_hint"] = {
                    "sample_only": True,
                    "more_rows_available": True,
                    "recommendation": "Refine the SQL query if complete row-level analysis is required."
                }
        else:
            # Metadata query still returns execution time metadata
            res["execution"] = execution_meta

        formatting_end = time.perf_counter()
        formatting_time_ms = (formatting_end - formatting_start) * 1000
        
        total_time_ms = (time.perf_counter() - start_time) * 1000
        
        res["execution"]["formatting_time_ms"] = round(formatting_time_ms, 2)
        res["execution"]["total_time_ms"] = round(total_time_ms, 2)
        res["execution_time_ms"] = round(total_time_ms, 2)

        MetricsService.record_sql_execution(total_time_ms)
        return res

    @classmethod
    async def estimate_cost(cls, sql: str) -> None:
        """Analyze query plan via EXPLAIN and reject if cost exceeds thresholds."""
        if settings.query_cost_limit <= 0.0:
            return
            
        sql_upper = sql.upper().strip()
        if "INFORMATION_SCHEMA" in sql_upper or any(sql_upper.startswith(kw) for kw in ["SHOW", "DESCRIBE", "DESC", "EXPLAIN"]):
            return

        # Enforce actual join limits using token parsing
        actual_joins = count_joins_in_sql(sql)
        if actual_joins > settings.max_joins_allowed:
            raise QueryPlanningError(
                f"Query exceeds maximum joins limit ({actual_joins} > {settings.max_joins_allowed})."
            )

        explain_sql = f"EXPLAIN {sql}"
        try:
            cols, rows = await execute_query(explain_sql, timeout=5.0)
            
            # Map columns to lowercase to find indexes
            col_map = {c.lower(): idx for idx, c in enumerate(cols)}
            
            id_idx = col_map.get("id")
            rows_idx = col_map.get("rows")
            type_idx = col_map.get("type")
            
            # Group explain rows by select_id (the "id" column)
            groups = collections.defaultdict(list)
            for r in rows:
                select_id = None
                if id_idx is not None and r[id_idx] is not None:
                    select_id = r[id_idx]
                if select_id is not None:
                    groups[select_id].append(r)
            
            total_estimated_rows = 0
            has_full_table_scan = False
            
            for select_id, group_rows in groups.items():
                group_cost = 1
                group_has_full = False
                
                # If there is more than 1 table step in this group, it's a join.
                is_group_join = len(group_rows) > 1
                
                for r in group_rows:
                    step_rows = 1
                    if rows_idx is not None and r[rows_idx] is not None:
                        try:
                            step_rows = int(r[rows_idx])
                        except (ValueError, TypeError):
                            step_rows = 1
                    
                    if is_group_join:
                        group_cost *= max(step_rows, 1)
                    else:
                        group_cost = max(step_rows, 1)
                        
                    # Check for full table scan
                    if type_idx is not None and r[type_idx] is not None:
                        if str(r[type_idx]).upper() == "ALL":
                            group_has_full = True
                            
                total_estimated_rows += group_cost
                if group_has_full:
                    has_full_table_scan = True
            
            if total_estimated_rows == 0:
                total_estimated_rows = 1

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

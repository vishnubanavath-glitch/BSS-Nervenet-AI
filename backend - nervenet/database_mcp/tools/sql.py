import time
import logging
from typing import Optional, Dict, Any
from database_mcp.tools.registry import mcp
from database_mcp.sql.executor import SQLExecutor
from database_mcp.services.router import IntentRouter
from database_mcp.services.metrics import MetricsService, QueryHistoryService, StructuredLogger
from database_mcp.metadata.cache import metadata_cache
from database_mcp.provider.mysql import execute_query
from database_mcp.exceptions import DatabaseMcpException, SqlValidationError

logger = logging.getLogger(__name__)

def _get_sql_metadata(tool_name: str) -> dict:
    """Helper to return intelligent metadata for SQL tool responses."""
    metadata = {
        "execution_cost": "HIGH",
        "cacheable": False,
        "retryable": True,
        "guidance": "Prefer indexed columns, apply selective filters, avoid unnecessary joins, and use LIMIT where appropriate."
    }
    if tool_name == "validate_sql":
        metadata["execution_cost"] = "LOW"
    elif tool_name == "analytics_summary":
        metadata["cacheable"] = True
        metadata["execution_cost"] = "MEDIUM"
        metadata["guidance"] = "Cache this summary for the conversation."
    return metadata


@mcp.tool()
async def validate_sql(sql: str) -> dict:
    """Validate a SQL statement to ensure it is syntactically sound and read-only.
    
    Args:
        sql: The SQL query to validate.
        
    Returns:
        A dict containing success status and validation message.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        from database_mcp.sql.validator import SQLValidator
        SQLValidator.validate(sql)
        res = {
            "success": True,
            "message": "SQL statement is valid and read-only.",
            "_mcp_metadata": _get_sql_metadata("validate_sql")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("validate_sql", duration_ms)
        QueryHistoryService.record("validate_sql", duration_ms, 0, True)
        StructuredLogger.log_execution("validate_sql", duration_ms, True, 0)
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"validate_sql validation failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in validate_sql: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("validate_sql", duration_ms, 0, False)
    StructuredLogger.log_execution("validate_sql", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def execute_sql(sql: str, max_rows: Optional[int] = None) -> dict:
    """Execute a validated read-only SQL query on the database, with automatic optimization and safety routing.
    
    Args:
        sql: The SQL query to execute.
        max_rows: Optional row limit override.
        
    Returns:
        A dict containing success status, columns, rows, count, and execution time.
    """
    start_time = time.perf_counter()
    error_msg = None
    
    # 1. Intent Router interception
    try:
        routed_result = await IntentRouter.route_sql(sql)
        if routed_result is not None:
            logger.info("Query successfully routed internally.")
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Record routed tool execution
            MetricsService.record_tool_execution("execute_sql_routed", duration_ms)
            if isinstance(routed_result, dict):
                routed_result["_mcp_metadata"] = _get_sql_metadata("execute_sql")
            return routed_result
    except Exception as e:
        logger.warning(f"Router redirection failed: {e}. Proceeding with standard execution.")

    # 2. Execute SQL with optimizer and cost estimator
    try:
        res = await SQLExecutor.execute(sql=sql, max_rows=max_rows)
        duration_ms = (time.perf_counter() - start_time) * 1000
        row_count = res.get("row_count", 0)
        
        MetricsService.record_tool_execution("execute_sql", duration_ms)
        QueryHistoryService.record("execute_sql", duration_ms, row_count, True)
        StructuredLogger.log_execution("execute_sql", duration_ms, False, row_count)
        res["_mcp_metadata"] = _get_sql_metadata("execute_sql")
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"execute_sql tool execution failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in execute_sql: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
        
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("execute_sql", duration_ms, 0, False)
    StructuredLogger.log_execution("execute_sql", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def explain_sql(sql: str) -> dict:
    """Explain a SQL query structure in plain English and provide the database query execution plan.
    
    Args:
        sql: The SQL query to explain.
        
    Returns:
        A dict detailing the query plan and query structure explanation.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        from database_mcp.sql.validator import SQLValidator
        import sqlparse
        
        # 1. Validate SQL
        SQLValidator.validate(sql)
        
        # 2. Plain English parsing & heuristics
        statements = sqlparse.parse(sql)
        explanation_parts = []
        
        for stmt in statements:
            stmt_type = stmt.get_type()
            explanation_parts.append(f"Statement Type: {stmt_type or 'SELECT'}")
            
            tables = set()
            from_seen = False
            for token in stmt.flatten():
                val_upper = token.value.upper().strip()
                if val_upper in ("FROM", "JOIN"):
                    from_seen = True
                    continue
                if from_seen:
                    if not token.is_whitespace and token.ttype not in (sqlparse.tokens.Keyword, sqlparse.tokens.Punctuation):
                        name = token.value.strip("`'\"")
                        if name.isalnum() or "_" in name:
                            tables.add(name)
                        from_seen = False
                        
            if tables:
                explanation_parts.append(f"Queries target table(s): {', '.join(tables)}")
            
            has_where = any(isinstance(t, sqlparse.sql.Where) for t in stmt.tokens)
            if has_where:
                explanation_parts.append("Applies filtering conditions (WHERE clause)")
            else:
                explanation_parts.append("Retrieves records without filters")
                
            explanation_parts.append("Executes read-only retrieval safely without data mutation")
            
        # 3. Retrieve MySQL EXPLAIN plan
        explain_sql_stmt = f"EXPLAIN {sql}"
        columns, rows = await execute_query(explain_sql_stmt)
        
        explain_plan = []
        for row in rows:
            plan_row = dict(zip(columns, row))
            explain_plan.append(plan_row)
            
        res = {
            "success": True,
            "query": sql,
            "plain_english_explanation": ". ".join(explanation_parts) + ".",
            "mysql_execution_plan": explain_plan,
            "_mcp_metadata": _get_sql_metadata("explain_sql")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("explain_sql", duration_ms)
        QueryHistoryService.record("explain_sql", duration_ms, len(explain_plan), True)
        StructuredLogger.log_execution("explain_sql", duration_ms, True, len(explain_plan))
        return res
        
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"explain_sql tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in explain_sql: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("explain_sql", duration_ms, 0, False)
    StructuredLogger.log_execution("explain_sql", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def analytics_summary() -> dict:
    """Compute aggregated database analytics metrics (e.g. revenue, consumption, top customers) safely without returning raw rows.
    
    Returns:
        A dict containing aggregated analytics summaries.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        # Check cache warmed
        if not metadata_cache.is_warmed():
            await metadata_cache.get() or await _get_metadata()
            
        meta = metadata_cache.get()
        analytics_results = {}
        
        # 1. Look for 'bills' and 'consumers' tables
        has_bills = "bills" in meta.tables
        has_consumers = "consumers" in meta.tables
        
        if has_bills:
            # Let's perform safe revenue trends
            # Note: We need columns of bills
            bills_cols = meta.tables["bills"].columns
            amount_col = None
            for c in ["amount", "bill_amount", "charges", "total"]:
                if c in bills_cols:
                    amount_col = c
                    break
                    
            if amount_col:
                revenue_query = f"SELECT SUM(`{amount_col}`) as total_rev, AVG(`{amount_col}`) as avg_rev, COUNT(*) as bill_count FROM `bills`"
                _, rev_rows = await execute_query(revenue_query)
                if rev_rows and rev_rows[0]:
                    analytics_results["billing_revenue_summary"] = {
                        "total_revenue": round(float(rev_rows[0][0]), 2) if rev_rows[0][0] is not None else 0.0,
                        "average_bill_amount": round(float(rev_rows[0][1]), 2) if rev_rows[0][1] is not None else 0.0,
                        "total_bills_issued": rev_rows[0][2]
                    }
                    
                # Top paying consumers
                if has_consumers:
                    consumer_id_col = "consumer_id"
                    name_col = "name"
                    if consumer_id_col in bills_cols and consumer_id_col in meta.tables["consumers"].columns:
                        top_paying_query = f"""
                            SELECT c.`{name_col}`, SUM(b.`{amount_col}`) as total_spent
                            FROM `bills` b
                            JOIN `consumers` c ON b.`{consumer_id_col}` = c.`{consumer_id_col}`
                            GROUP BY c.`{name_col}`
                            ORDER BY total_spent DESC
                            LIMIT 5
                        """
                        try:
                            cols, rows = await execute_query(top_paying_query)
                            analytics_results["top_highest_billing_consumers"] = [
                                {"consumer_name": r[0], "total_spent": round(float(r[1]), 2)}
                                for r in rows
                            ]
                        except Exception as e:
                            logger.warning(f"Could not join bills with consumers: {e}")
                            
        # 2. Look for any table named 'meters' or 'readings' or 'usage'
        usage_tbl = None
        for t in meta.tables:
            if any(x in t.lower() for x in ["meter", "reading", "usage", "consumption"]):
                usage_tbl = t
                break
                
        if usage_tbl:
            tbl_cols = meta.tables[usage_tbl].columns
            usage_col = None
            for c in ["consumption", "usage", "reading_value", "kwh", "units"]:
                if c in tbl_cols:
                    usage_col = c
                    break
            if usage_col:
                usage_query = f"SELECT AVG(`{usage_col}`) as avg_usage, MAX(`{usage_col}`) as max_usage FROM `{usage_tbl}`"
                try:
                    _, usage_rows = await execute_query(usage_query)
                    if usage_rows and usage_rows[0]:
                        analytics_results["meter_consumption_summary"] = {
                            "average_consumption": round(float(usage_rows[0][0]), 2) if usage_rows[0][0] is not None else 0.0,
                            "maximum_consumption": round(float(usage_rows[0][1]), 2) if usage_rows[0][1] is not None else 0.0
                        }
                except Exception as e:
                    logger.warning(f"Usage summary query failed: {e}")
                    
        # 3. Fallback: Generic column aggregates across database
        if not analytics_results:
            generic_stats = []
            for name, tbl in list(meta.tables.items())[:3]:
                # find first numeric column
                num_col = None
                for col_name, col in tbl.columns.items():
                    if any(x in col.data_type.lower() for x in ["int", "decimal", "float", "double"]):
                        if not col.is_primary_key and not col.is_foreign_key:
                            num_col = col_name
                            break
                if num_col:
                    generic_query = f"SELECT AVG(`{num_col}`) as avg_val, SUM(`{num_col}`) as sum_val FROM `{name}`"
                    try:
                        _, val_rows = await execute_query(generic_query)
                        if val_rows and val_rows[0]:
                            generic_stats.append({
                                "table": name,
                                "metric_column": num_col,
                                "average": round(float(val_rows[0][0]), 2) if val_rows[0][0] is not None else 0.0,
                                "sum": round(float(val_rows[0][1]), 2) if val_rows[0][1] is not None else 0.0
                            })
                    except Exception:
                        pass
            if generic_stats:
                analytics_results["generic_table_aggregates"] = generic_stats
            else:
                analytics_results["status"] = "No analytics tables (bills/meters) or suitable numeric columns found."

        res = {
            "success": True,
            "analytics_summary": analytics_results,
            "_mcp_metadata": _get_sql_metadata("analytics_summary")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("analytics_summary", duration_ms)
        QueryHistoryService.record("analytics_summary", duration_ms, len(analytics_results), True)
        StructuredLogger.log_execution("analytics_summary", duration_ms, True, len(analytics_results))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"analytics_summary failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in analytics_summary: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("analytics_summary", duration_ms, 0, False)
    StructuredLogger.log_execution("analytics_summary", duration_ms, False, 0, error_msg)
    return res

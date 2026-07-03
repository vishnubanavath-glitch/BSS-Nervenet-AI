import logging
from typing import Optional
from database_mcp.tools.registry import mcp
from database_mcp.sql.validator import SQLValidator
from database_mcp.sql.executor import SQLExecutor
from database_mcp.exceptions import DatabaseMcpException
from database_mcp.provider.mysql import execute_query
import sqlparse

logger = logging.getLogger(__name__)

@mcp.tool()
async def validate_sql(sql: str) -> dict:
    """Validate a SQL statement to ensure it is syntactically sound and read-only.
    
    Args:
        sql: The SQL query to validate.
        
    Returns:
        A dict containing success status and validation message.
    """
    try:
        SQLValidator.validate(sql)
        return {
            "success": True,
            "message": "SQL statement is valid and read-only."
        }
    except DatabaseMcpException as e:
        logger.warning(f"validate_sql validation failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in validate_sql: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def execute_sql(sql: str, max_rows: Optional[int] = None) -> dict:
    """Execute a validated read-only SQL query on the database.
    
    Args:
        sql: The SQL query to execute.
        max_rows: Optional row limit override.
        
    Returns:
        A dict containing success status, columns, rows, count, and execution time.
    """
    try:
        res = await SQLExecutor.execute(sql=sql, max_rows=max_rows)
        return res
    except DatabaseMcpException as e:
        logger.warning(f"execute_sql tool execution failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in execute_sql: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def explain_sql(sql: str) -> dict:
    """Explain a SQL query structure in plain English and provide the database query execution plan.
    
    Args:
        sql: The SQL query to explain.
        
    Returns:
        A dict detailing the query plan and query structure explanation.
    """
    try:
        # 1. Validate SQL
        SQLValidator.validate(sql)
        
        # 2. Plain English parsing & heuristics
        statements = sqlparse.parse(sql)
        explanation_parts = []
        
        for stmt in statements:
            stmt_type = stmt.get_type()
            explanation_parts.append(f"Statement Type: {stmt_type or 'SELECT'}")
            
            # Simple heuristic to extract table names
            tables = set()
            from_seen = False
            join_seen = False
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
            
            # Check for WHERE clause
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
            
        return {
            "success": True,
            "query": sql,
            "plain_english_explanation": ". ".join(explanation_parts) + ".",
            "mysql_execution_plan": explain_plan
        }
        
    except DatabaseMcpException as e:
        logger.warning(f"explain_sql tool failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in explain_sql: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

import asyncio
import logging
from typing import List, Tuple, Optional, Any
from database_mcp.provider.connection import ConnectionProvider
from database_mcp.exceptions import SqlExecutionError, ConnectionError
from database_mcp.config import settings

logger = logging.getLogger(__name__)

async def execute_query(
    query: str,
    params: Optional[Tuple[Any, ...]] = None,
    timeout: Optional[float] = None,
    limit: Optional[int] = None
) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    """Execute a SQL query asynchronously under a timeout and optional row limit.
    
    Returns:
        A tuple of (columns_list, rows_list).
    """
    query_timeout = timeout if timeout is not None else settings.db_timeout

    try:
        return await asyncio.wait_for(
            _execute(query, params, limit),
            timeout=query_timeout
        )
    except asyncio.TimeoutError as e:
        logger.error(f"Query execution timed out after {query_timeout}s: {query}", exc_info=True)
        raise ConnectionError(f"Query execution timed out after {query_timeout} seconds.") from e
    except Exception as e:
        if isinstance(e, (SqlExecutionError, ConnectionError)):
            raise e
        logger.error(f"Query execution encountered an unexpected error: {e}", exc_info=True)
        raise SqlExecutionError(f"Query execution failed: {str(e)}") from e

async def _execute(
    query: str,
    params: Optional[Tuple[Any, ...]] = None,
    limit: Optional[int] = None
) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    async with ConnectionProvider.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(query, params)
                if limit is not None:
                    rows = await cursor.fetchmany(limit)
                else:
                    rows = await cursor.fetchall()
                columns = [col[0] for col in cursor.description] if cursor.description else []
                # Convert rows (which could be tuples) into list of lists or list of tuples
                return columns, [list(row) for row in rows]
            except Exception as e:
                logger.error(f"MySQL driver error executing query: {e} | SQL: {query}", exc_info=True)
                raise SqlExecutionError(f"Database error: {str(e)}") from e

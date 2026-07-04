import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from database_mcp.config import settings

logger = logging.getLogger("database_mcp.structured")

class MetricsService:
    """Service to track and record performance metrics."""
    _metadata_lookups = 0
    _metadata_cache_hits = 0
    _sql_execution_times: List[float] = []
    _tool_execution_times: Dict[str, List[float]] = {}

    @classmethod
    def record_metadata_lookup(cls, cache_hit: bool) -> None:
        cls._metadata_lookups += 1
        if cache_hit:
            cls._metadata_cache_hits += 1

    @classmethod
    def record_sql_execution(cls, duration_ms: float) -> None:
        cls._sql_execution_times.append(duration_ms)

    @classmethod
    def record_tool_execution(cls, tool_name: str, duration_ms: float) -> None:
        if tool_name not in cls._tool_execution_times:
            cls._tool_execution_times[tool_name] = []
        cls._tool_execution_times[tool_name].append(duration_ms)

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        hit_ratio = 0.0
        if cls._metadata_lookups > 0:
            hit_ratio = round(cls._metadata_cache_hits / cls._metadata_lookups, 4)
            
        avg_sql_time = 0.0
        if cls._sql_execution_times:
            avg_sql_time = round(sum(cls._sql_execution_times) / len(cls._sql_execution_times), 2)
            
        avg_tool_times = {}
        for t, times in cls._tool_execution_times.items():
            if times:
                avg_tool_times[t] = round(sum(times) / len(times), 2)

        return {
            "metadata_lookup_count": cls._metadata_lookups,
            "metadata_cache_hits": cls._metadata_cache_hits,
            "metadata_cache_hit_ratio": hit_ratio,
            "sql_execution_count": len(cls._sql_execution_times),
            "average_sql_execution_time_ms": avg_sql_time,
            "average_tool_execution_times_ms": avg_tool_times
        }

class QueryHistoryService:
    """Service to store lightweight query execution history without sensitive information."""
    _history: List[Dict[str, Any]] = []
    _max_history_size = 500

    @classmethod
    def record(cls, tool: str, execution_time_ms: float, rows_returned: int, success: bool) -> None:
        record = {
            "timestamp": time.time(),
            "tool": tool,
            "execution_time_ms": execution_time_ms,
            "rows_returned": rows_returned,
            "success": success
        }
        cls._history.append(record)
        if len(cls._history) > cls._max_history_size:
            cls._history.pop(0)

    @classmethod
    def get_history(cls) -> List[Dict[str, Any]]:
        return list(cls._history)


class StructuredLogger:
    """Helper to log tool executions in a structured format."""
    
    @classmethod
    def log_execution(
        cls, 
        tool: str, 
        execution_time_ms: float, 
        cache_hit: bool, 
        rows_returned: int, 
        error: Optional[str] = None
    ) -> str:
        req_id = str(uuid.uuid4())
        log_data = {
            "request_id": req_id,
            "tool": tool,
            "execution_time_ms": round(execution_time_ms, 2),
            "cache_hit": cache_hit,
            "database_accessed": settings.db_name,
            "rows_returned": rows_returned,
            "error": error
        }
        
        # Log to stderr so as not to pollute fastmcp stdout channel
        # We format as key-value pairs or JSON
        log_message = (
            f"[REQ:{req_id}] Tool={tool} Time={log_data['execution_time_ms']}ms "
            f"CacheHit={cache_hit} DB={log_data['database_accessed']} Rows={rows_returned} "
            f"Error={error or 'None'}"
        )
        logger.info(log_message)
        return req_id

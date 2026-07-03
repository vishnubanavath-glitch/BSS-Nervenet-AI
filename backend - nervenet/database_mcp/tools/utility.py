import logging
from database_mcp.tools.registry import mcp
from database_mcp.metadata.cache import metadata_cache
from database_mcp.metadata.loader import MetadataLoader
from database_mcp.exceptions import DatabaseMcpException
from database_mcp.provider.mysql import execute_query

logger = logging.getLogger(__name__)

@mcp.tool()
async def health_check() -> dict:
    """Verify MySQL database connectivity, metadata cache status, and MCP overall health.
    
    Returns:
        A dict showing health check status for database, cache, and server.
    """
    db_health = {"status": "unhealthy", "message": "Not tested"}
    cache_health = {"status": "unwarmed", "table_count": 0}
    
    # 1. Test database connection
    try:
        # Simple ping query to check DB connectivity
        columns, rows = await execute_query("SELECT 1")
        if rows and rows[0][0] == 1:
            db_health = {"status": "healthy", "message": "Successfully connected and pinged MySQL."}
        else:
            db_health = {"status": "unhealthy", "message": "Ping query returned unexpected results."}
    except Exception as e:
        db_health = {"status": "unhealthy", "message": f"Failed to ping database: {str(e)}"}
        
    # 2. Check metadata cache
    if metadata_cache.is_warmed():
        meta = metadata_cache.get()
        if meta:
            cache_health = {
                "status": "healthy",
                "database_name": meta.database_name,
                "table_count": len(meta.tables),
                "summary": meta.summary
            }
        else:
            cache_health = {"status": "error", "message": "Metadata cache is marked warmed but holds None value."}
            
    overall_status = "healthy" if db_health["status"] == "healthy" and cache_health["status"] == "healthy" else "unhealthy"
    
    return {
        "success": True,
        "status": overall_status,
        "components": {
            "database": db_health,
            "metadata_cache": cache_health
        }
    }

@mcp.tool()
async def refresh_metadata() -> dict:
    """Reload database schema metadata from MySQL to refresh the in-memory cache without restarting the server.
    
    Returns:
        A dict detailing the metadata refresh result.
    """
    try:
        logger.info("Manual metadata refresh requested. Invalidating cache...")
        metadata_cache.clear()
        
        # Load and warm again
        meta = await MetadataLoader.load_and_cache()
        
        return {
            "success": True,
            "message": "Database schema metadata refreshed successfully.",
            "database_name": meta.database_name,
            "table_count": len(meta.tables),
            "summary": meta.summary
        }
    except DatabaseMcpException as e:
        logger.warning(f"refresh_metadata failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in refresh_metadata: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

import logging
from typing import Dict, Any, List
from database_mcp.tools.registry import mcp
from database_mcp.metadata.cache import metadata_cache
from database_mcp.metadata.loader import MetadataLoader
from database_mcp.exceptions import DatabaseMcpException, MetadataError

logger = logging.getLogger(__name__)

async def _get_metadata() -> Any:
    """Helper to retrieve metadata, warming the cache if necessary."""
    if not metadata_cache.is_warmed():
        logger.info("Metadata cache miss in tool execution. Warming cache...")
        await MetadataLoader.load_and_cache()
    data = metadata_cache.get()
    if data is None:
        raise MetadataError("Failed to retrieve database metadata from cache.")
    return data

@mcp.tool()
async def discover_database() -> dict:
    """Discover database details (name, number of tables, and schema metadata summary).
    
    Returns:
        A dict containing success status and database details.
    """
    try:
        meta = await _get_metadata()
        return {
            "success": True,
            "database_name": meta.database_name,
            "table_count": len(meta.tables),
            "summary": meta.summary
        }
    except DatabaseMcpException as e:
        logger.warning(f"discover_database tool failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in discover_database: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def list_tables() -> dict:
    """List all table names present in the database.
    
    Returns:
        A dict containing success status and a list of tables.
    """
    try:
        meta = await _get_metadata()
        return {
            "success": True,
            "tables": list(meta.tables.keys())
        }
    except DatabaseMcpException as e:
        logger.warning(f"list_tables tool failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in list_tables: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def describe_table(table_name: str) -> dict:
    """Describe columns, data types, primary key, and foreign keys of a given table.
    
    Args:
        table_name: The name of the table to describe.
        
    Returns:
        A dict containing the table schema.
    """
    try:
        meta = await _get_metadata()
        if table_name not in meta.tables:
            raise MetadataError(f"Table '{table_name}' not found in database metadata.")
            
        tbl = meta.tables[table_name]
        columns_info = {}
        for col_name, col in tbl.columns.items():
            columns_info[col_name] = {
                "data_type": col.data_type,
                "is_nullable": col.is_nullable,
                "is_primary_key": col.is_primary_key,
                "is_foreign_key": col.is_foreign_key,
                "foreign_key_target": col.foreign_key_target
            }
            
        return {
            "success": True,
            "table": table_name,
            "columns": columns_info,
            "primary_keys": tbl.primary_keys,
            "foreign_keys": tbl.foreign_keys
        }
    except DatabaseMcpException as e:
        logger.warning(f"describe_table tool failed for table '{table_name}': {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in describe_table: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def list_relationships() -> dict:
    """List all foreign key relationships discovered between tables.
    
    Returns:
        A dict containing foreign key relationship mappings.
    """
    try:
        meta = await _get_metadata()
        return {
            "success": True,
            "relationships": meta.relationships
        }
    except DatabaseMcpException as e:
        logger.warning(f"list_relationships tool failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in list_relationships: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

@mcp.tool()
async def search_schema(keyword: str) -> dict:
    """Search table names or column names for occurrences of a keyword (case-insensitive).
    
    Args:
        keyword: The search term keyword.
        
    Returns:
        A dict listing matches in table names and column names.
    """
    try:
        meta = await _get_metadata()
        k = keyword.lower()
        matching_tables = []
        matching_columns = []
        
        for tbl_name, tbl in meta.tables.items():
            if k in tbl_name.lower():
                matching_tables.append(tbl_name)
            for col_name in tbl.columns:
                if k in col_name.lower():
                    matching_columns.append(f"{tbl_name}.{col_name}")
                    
        return {
            "success": True,
            "keyword": keyword,
            "matching_tables": matching_tables,
            "matching_columns": matching_columns
        }
    except DatabaseMcpException as e:
        logger.warning(f"search_schema tool failed: {e.message}")
        return e.to_dict()
    except Exception as e:
        logger.error(f"Unexpected error in search_schema: {e}", exc_info=True)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }

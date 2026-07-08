import time
import logging
from typing import Dict, Any, List, Optional
from database_mcp.tools.registry import mcp
from database_mcp.metadata.cache import metadata_cache
from database_mcp.metadata.loader import MetadataLoader
from database_mcp.services.profiler import DatabaseProfiler
from database_mcp.services.metrics import MetricsService, QueryHistoryService, StructuredLogger
from database_mcp.exceptions import DatabaseMcpException, MetadataError

logger = logging.getLogger(__name__)

def _get_intelligent_metadata(tool_name: str) -> dict:
    """Helper to return intelligent metadata for a tool response."""
    metadata = {
        "execution_cost": "LOW",
        "cacheable": True,
        "retryable": True,
        "guidance": "Cache this metadata for the conversation to avoid redundant calls."
    }
    if tool_name in ["database_statistics", "database_overview"]:
        metadata["execution_cost"] = "MEDIUM"
        metadata["guidance"] = "Cache this overview for the conversation. Drill down into specific tables only when necessary."
    elif tool_name in ["table_profile", "search_schema"]:
        metadata["execution_cost"] = "HIGH"
        metadata["cacheable"] = False
        metadata["guidance"] = "Expensive operation. Avoid calling repeatedly for the same arguments."
    return metadata


async def _get_metadata() -> Any:
    """Helper to retrieve metadata, warming the cache and checking for schema drift."""
    start_time = time.perf_counter()
    cache_hit = metadata_cache.is_warmed()
    
    if not cache_hit:
        logger.info("Metadata cache miss in tool execution. Warming cache...")
        await MetadataLoader.load_and_cache()
    else:
        # Automatic drift check and refresh
        await MetadataLoader.check_drift_and_refresh()
        
    data = metadata_cache.get()
    
    end_time = time.perf_counter()
    lookup_time_ms = (end_time - start_time) * 1000
    MetricsService.record_metadata_lookup(cache_hit=cache_hit)
    
    if data is None:
        raise MetadataError("Failed to retrieve database metadata.")
    return data

@mcp.tool()
async def discover_database() -> dict:
    """Discover database details (name, number of tables, and schema metadata summary).
    
    Returns:
        A dict containing success status and database details.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        res = {
            "success": True,
            "database_name": meta.database_name,
            "table_count": len(meta.tables),
            "summary": meta.summary,
            "metadata_version": meta.metadata_version,
            "schema_version": meta.schema_version,
            "cache_timestamp": meta.cache_timestamp,
            "last_refresh": meta.last_refresh,
            "_mcp_metadata": _get_intelligent_metadata("discover_database")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("discover_database", duration_ms)
        QueryHistoryService.record("discover_database", duration_ms, 0, True)
        StructuredLogger.log_execution("discover_database", duration_ms, True, 0)
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"discover_database tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in discover_database: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("discover_database", duration_ms, 0, False)
    StructuredLogger.log_execution("discover_database", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def list_tables() -> dict:
    """List all table names present in the database.
    
    Returns:
        A dict containing success status and a list of tables.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        tables_list = list(meta.tables.keys())
        res = {
            "success": True,
            "tables": tables_list,
            "_mcp_metadata": _get_intelligent_metadata("list_tables")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("list_tables", duration_ms)
        QueryHistoryService.record("list_tables", duration_ms, len(tables_list), True)
        StructuredLogger.log_execution("list_tables", duration_ms, True, len(tables_list))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"list_tables tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in list_tables: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("list_tables", duration_ms, 0, False)
    StructuredLogger.log_execution("list_tables", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def describe_table(table_name: str) -> dict:
    """Describe columns, data types, primary key, and foreign keys of a given table.
    
    Args:
        table_name: The name of the table to describe.
        
    Returns:
        A dict containing the table schema.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        if table_name not in meta.tables:
            raise MetadataError(f"Table '{table_name}' not found in database metadata.")
            
        tbl = meta.tables[table_name]
        related_tables = [rel["to_table"] for rel in meta.relationships if rel.get("from_table") == table_name]
        related_tables.extend([rel["from_table"] for rel in meta.relationships if rel.get("to_table") == table_name])
        
        schema_summary = {
            "primary_keys": tbl.primary_keys,
            "identifier_columns": [],
            "indexed_columns": [],
            "numeric_columns": [],
            "date_columns": [],
            "related_tables": list(set(related_tables))
        }

        columns_info = {}
        for col_name, col in tbl.columns.items():
            dt_lower = col.data_type.lower()
            if col.is_primary_key or col.is_foreign_key:
                schema_summary["indexed_columns"].append(col_name)
            if col_name.endswith("_id") or col_name == "id" or "uuid" in col_name.lower():
                schema_summary["identifier_columns"].append(col_name)
            if any(x in dt_lower for x in ["int", "decimal", "numeric", "float", "double"]):
                schema_summary["numeric_columns"].append(col_name)
            if any(x in dt_lower for x in ["date", "time", "timestamp"]):
                schema_summary["date_columns"].append(col_name)

            columns_info[col_name] = {
                "data_type": col.data_type,
                "is_nullable": col.is_nullable,
                "is_primary_key": col.is_primary_key,
                "is_foreign_key": col.is_foreign_key,
                "foreign_key_target": col.foreign_key_target
            }
            
        res = {
            "success": True,
            "table": table_name,
            "schema_summary": schema_summary,
            "columns": columns_info,
            "primary_keys": tbl.primary_keys,
            "foreign_keys": tbl.foreign_keys,
            "_mcp_metadata": _get_intelligent_metadata("describe_table")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("describe_table", duration_ms)
        QueryHistoryService.record("describe_table", duration_ms, len(columns_info), True)
        StructuredLogger.log_execution("describe_table", duration_ms, True, len(columns_info))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"describe_table tool failed for table '{table_name}': {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in describe_table: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("describe_table", duration_ms, 0, False)
    StructuredLogger.log_execution("describe_table", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def list_relationships() -> dict:
    """List all foreign key relationships discovered between tables.
    
    Returns:
        A dict containing foreign key relationship mappings.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        rel_list = meta.relationships
        res = {
            "success": True,
            "relationships": rel_list,
            "_mcp_metadata": _get_intelligent_metadata("list_relationships")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("list_relationships", duration_ms)
        QueryHistoryService.record("list_relationships", duration_ms, len(rel_list), True)
        StructuredLogger.log_execution("list_relationships", duration_ms, True, len(rel_list))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"list_relationships tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in list_relationships: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("list_relationships", duration_ms, 0, False)
    StructuredLogger.log_execution("list_relationships", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def search_schema(keyword: str) -> dict:
    """Search schema table names, column names, descriptions, and aliases for occurrences of a keyword (case-insensitive).
    
    Args:
        keyword: The search query keyword or sentence.
        
    Returns:
        A dict listing matched tables and columns with descriptions and explanations.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        
        # Tokenize sentence to find significant keywords
        words = [w.strip("?,.!\"'()").lower() for w in keyword.split() if len(w) > 2]
        if not words:
            words = [keyword.lower()]
            
        matching_tables = {}
        matching_columns = {}
        
        for tbl_name, tbl in meta.tables.items():
            tbl_score = 0
            matches = []
            
            # Match table name
            for w in words:
                if w in tbl_name.lower():
                    tbl_score += 10
                    matches.append(f"Table name match: '{w}'")
            
            # Match aliases
            for alias in tbl.aliases:
                for w in words:
                    if w in alias.lower():
                        tbl_score += 8
                        matches.append(f"Alias match: '{alias}'")
                        
            # Match description
            if tbl.description:
                for w in words:
                    if w in tbl.description.lower():
                        tbl_score += 5
                        matches.append("Table description match")
            
            # Match columns
            tbl_cols_matched = []
            for col_name, col in tbl.columns.items():
                col_score = 0
                col_matches = []
                for w in words:
                    if w in col_name.lower():
                        col_score += 6
                        col_matches.append(f"Column name match: '{w}'")
                
                if col_score > 0:
                    tbl_cols_matched.append({
                        "column": f"{tbl_name}.{col_name}",
                        "data_type": col.data_type,
                        "matches": col_matches
                    })
                    tbl_score += col_score
                    
            if tbl_score > 0:
                matching_tables[tbl_name] = {
                    "score": tbl_score,
                    "description": tbl.description or f"Database table '{tbl_name}'",
                    "explanation": f"Matches: {', '.join(set(matches))}" if matches else "Matches via column names.",
                    "matched_columns": tbl_cols_matched
                }

        # Sort by score descending
        sorted_tables = sorted(matching_tables.items(), key=lambda x: x[1]["score"], reverse=True)
        res_tables = []
        for name, details in sorted_tables:
            res_tables.append({
                "table_name": name,
                "description": details["description"],
                "explanation": details["explanation"],
                "columns": [c["column"] for c in details["matched_columns"]]
            })

        matching_tables_list = []
        matching_columns_list = []
        k = keyword.lower()
        for tbl_name, tbl in meta.tables.items():
            if k in tbl_name.lower():
                matching_tables_list.append(tbl_name)
            for col_name in tbl.columns:
                if k in col_name.lower():
                    matching_columns_list.append(f"{tbl_name}.{col_name}")

        res = {
            "success": True,
            "keyword": keyword,
            "matches": res_tables,
            "matching_tables": matching_tables_list,
            "matching_columns": matching_columns_list,
            "_mcp_metadata": _get_intelligent_metadata("search_schema")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("search_schema", duration_ms)
        QueryHistoryService.record("search_schema", duration_ms, len(res_tables), True)
        StructuredLogger.log_execution("search_schema", duration_ms, True, len(res_tables))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"search_schema tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in search_schema: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("search_schema", duration_ms, 0, False)
    StructuredLogger.log_execution("search_schema", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def database_overview() -> dict:
    """Retrieve a high-level overview of the database (tables, approximate sizes, updates, and business domains) without scanning every row.
    
    Returns:
        A dict showing a database catalog overview.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        tables_overview = {}
        total_size = 0
        
        for name, tbl in meta.tables.items():
            tbl_size = tbl.data_length + tbl.index_length
            total_size += tbl_size
            tables_overview[name] = {
                "approximate_rows": tbl.row_count,
                "approximate_size_bytes": tbl_size,
                "primary_keys": tbl.primary_keys,
                "foreign_key_count": len(tbl.foreign_keys),
                "latest_update_time": tbl.update_time
            }
            
        res = {
            "success": True,
            "database_name": meta.database_name,
            "metadata_version": meta.metadata_version,
            "schema_version": meta.schema_version,
            "cache_timestamp": meta.cache_timestamp,
            "table_count": len(meta.tables),
            "total_size_bytes": total_size,
            "business_domains": meta.business_domains,
            "tables": tables_overview,
            "relationships": meta.relationships,
            "_mcp_metadata": _get_intelligent_metadata("database_overview")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("database_overview", duration_ms)
        QueryHistoryService.record("database_overview", duration_ms, len(tables_overview), True)
        StructuredLogger.log_execution("database_overview", duration_ms, True, len(tables_overview))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"database_overview tool failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in database_overview: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("database_overview", duration_ms, 0, False)
    StructuredLogger.log_execution("database_overview", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def table_profile(table_name: str) -> dict:
    """Retrieve detailed stats and profile of a table (null percentage, distinct values, date range, size) without returning rows.
    
    Args:
        table_name: Name of the table.
        
    Returns:
        A dict profiling table schema and contents.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        # Check metadata cache and warm it if needed
        await _get_metadata()
        profile = await DatabaseProfiler.profile_table(table_name)
        
        if "success" in profile and not profile["success"]:
            raise MetadataError(profile.get("error", "Failed to profile table."))

        res = {
            "success": True,
            "profile": profile,
            "_mcp_metadata": _get_intelligent_metadata("table_profile")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("table_profile", duration_ms)
        QueryHistoryService.record("table_profile", duration_ms, len(profile.get("columns", [])), True)
        StructuredLogger.log_execution("table_profile", duration_ms, True, len(profile.get("columns", [])))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"table_profile tool failed for '{table_name}': {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in table_profile: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("table_profile", duration_ms, 0, False)
    StructuredLogger.log_execution("table_profile", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def relationship_graph() -> dict:
    """Expose the database Foreign Key relationships graph to trace linkages (e.g. Consumer -> Meter -> Billing).
    
    Returns:
        A dict containing graph nodes, edges, and a visualization representation.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        
        # Build Mermaid graph
        mermaid_lines = ["graph TD"]
        for tbl in meta.tables:
            mermaid_lines.append(f"    {tbl}[\"{tbl}\"]")
            
        for rel in meta.relationships:
            from_t = rel["from_table"]
            to_t = rel["to_table"]
            from_c = rel["from_column"]
            to_c = rel["to_column"]
            mermaid_lines.append(f"    {from_t} -->|\"{from_c} -> {to_c}\"| {to_t}")
            
        mermaid_str = "\n".join(mermaid_lines)
        
        res = {
            "success": True,
            "nodes": list(meta.tables.keys()),
            "edges": meta.relationships,
            "mermaid_graph": mermaid_str,
            "_mcp_metadata": _get_intelligent_metadata("relationship_graph")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("relationship_graph", duration_ms)
        QueryHistoryService.record("relationship_graph", duration_ms, len(meta.relationships), True)
        StructuredLogger.log_execution("relationship_graph", duration_ms, True, len(meta.relationships))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"relationship_graph failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in relationship_graph: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("relationship_graph", duration_ms, 0, False)
    StructuredLogger.log_execution("relationship_graph", duration_ms, False, 0, error_msg)
    return res

@mcp.tool()
async def database_statistics() -> dict:
    """Retrieve comprehensive database statistics (total tables, rows, columns, estimated storage size, indexed status, and cache health).
    
    Returns:
        A dict with complete database health and size statistics.
    """
    start_time = time.perf_counter()
    error_msg = None
    try:
        meta = await _get_metadata()
        
        total_rows = 0
        total_columns = 0
        total_size = 0
        largest_table = None
        largest_size = -1
        smallest_table = None
        smallest_size = 999999999999
        
        indexed_cols_count = 0
        tables_with_pri_keys = 0
        
        for name, tbl in meta.tables.items():
            total_rows += tbl.row_count
            total_columns += len(tbl.columns)
            tbl_size = tbl.data_length + tbl.index_length
            total_size += tbl_size
            
            if tbl_size > largest_size:
                largest_size = tbl_size
                largest_table = name
                
            if tbl_size < smallest_size:
                smallest_size = tbl_size
                smallest_table = name
                
            if tbl.primary_keys:
                tables_with_pri_keys += 1
                
            for col in tbl.columns.values():
                if col.is_primary_key or col.is_foreign_key:
                    indexed_cols_count += 1
                    
        # Compute schema health ratio
        schema_health_pct = 100.0
        if len(meta.tables) > 0:
            schema_health_pct = round((tables_with_pri_keys / len(meta.tables) * 100), 2)

        res = {
            "success": True,
            "total_tables": len(meta.tables),
            "total_rows": total_rows,
            "total_columns": total_columns,
            "estimated_storage_bytes": total_size,
            "largest_table": {
                "name": largest_table,
                "approximate_size_bytes": largest_size
            } if largest_table else None,
            "smallest_table": {
                "name": smallest_table,
                "approximate_size_bytes": smallest_size
            } if smallest_table else None,
            "indexed_columns_count": indexed_cols_count,
            "schema_health": {
                "tables_with_primary_key_pct": schema_health_pct,
                "status": "healthy" if schema_health_pct > 80 else "warning"
            },
            "performance_metrics": MetricsService.get_metrics(),
            "_mcp_metadata": _get_intelligent_metadata("database_statistics")
        }
        duration_ms = (time.perf_counter() - start_time) * 1000
        MetricsService.record_tool_execution("database_statistics", duration_ms)
        QueryHistoryService.record("database_statistics", duration_ms, len(meta.tables), True)
        StructuredLogger.log_execution("database_statistics", duration_ms, True, len(meta.tables))
        return res
    except DatabaseMcpException as e:
        error_msg = e.message
        logger.warning(f"database_statistics failed: {e.message}")
        res = e.to_dict()
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in database_statistics: {e}", exc_info=True)
        res = {
            "success": False,
            "error": {
                "code": "UNKNOWN_ERROR",
                "message": str(e),
                "category": "General"
            }
        }
    duration_ms = (time.perf_counter() - start_time) * 1000
    QueryHistoryService.record("database_statistics", duration_ms, 0, False)
    StructuredLogger.log_execution("database_statistics", duration_ms, False, 0, error_msg)
    return res

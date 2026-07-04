import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class IntentRouter:
    """Classifies user query/SQL intent and routes to metadata/analytics tools instead of raw SQL execution."""

    @classmethod
    def classify_intent(cls, sql: str) -> str:
        """Classify a SQL query into one of: Schema, Overview, Analytics, Statistics, Search, Query, Relationship."""
        sql_upper = sql.upper().strip()
        
        # 1. Schema
        if sql_upper.startswith("DESCRIBE ") or sql_upper.startswith("DESC ") or "SHOW COLUMNS" in sql_upper:
            return "Schema"
        if "INFORMATION_SCHEMA.COLUMNS" in sql_upper:
            return "Schema"
            
        # 2. Overview
        if sql_upper.startswith("SHOW TABLES") or sql_upper.startswith("SHOW DATABASES") or sql_upper.startswith("SHOW SCHEMAS"):
            return "Overview"
        if "INFORMATION_SCHEMA.TABLES" in sql_upper and "TABLE_NAME" in sql_upper and "TABLE_ROWS" not in sql_upper:
            return "Overview"
            
        # 3. Relationship
        if "KEY_COLUMN_USAGE" in sql_upper or "REFERENCED_TABLE_NAME" in sql_upper or "FOREIGN_KEY" in sql_upper:
            return "Relationship"
            
        # 4. Statistics
        if "COUNT(*)" in sql_upper and ("INFORMATION_SCHEMA" in sql_upper or "TABLE_ROWS" in sql_upper):
            return "Statistics"
        if "DATABASE_STATISTICS" in sql_upper or "SUM(DATA_LENGTH)" in sql_upper:
            return "Statistics"
            
        # 5. Search
        if "LIKE" in sql_upper and ("INFORMATION_SCHEMA.COLUMNS" in sql_upper or "INFORMATION_SCHEMA.TABLES" in sql_upper):
            return "Search"
            
        # 6. Analytics
        # Only route if specifically asking for analytics_summary
        if "ANALYTICS_SUMMARY" in sql_upper:
            return "Analytics"
            
        # Default: standard Query (even counts and joins on user tables are standard data queries)
        return "Query"

    @classmethod
    async def route_sql(cls, sql: str) -> Optional[Dict[str, Any]]:
        """Intercepts a SQL query. If it is metadata/stats intent, routes it to the corresponding tool."""
        intent = cls.classify_intent(sql)
        logger.info(f"SQL Intent classified as: {intent}")
        
        if intent == "Query":
            return None # Do not route, execute standard SQL

        # Import tools locally to avoid circular dependencies
        from database_mcp.tools.metadata import (
            database_overview, 
            list_tables, 
            describe_table, 
            list_relationships,
            search_schema,
            database_statistics
        )
        from database_mcp.tools.sql import analytics_summary
        
        sql_clean = sql.strip().rstrip(";")
        sql_upper = sql_clean.upper()

        try:
            if intent == "Overview":
                if "SHOW TABLES" in sql_upper:
                    logger.info("Routing query to list_tables()")
                    return await list_tables()
                logger.info("Routing query to database_overview()")
                return await database_overview()
                
            elif intent == "Schema":
                # Try to extract table name
                # Match DESCRIBE table_name or DESC table_name
                match = re.search(r'\b(?:DESCRIBE|DESC)\s+`?([a-zA-Z0-9_]+)`?', sql_clean, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    logger.info(f"Routing query to describe_table('{table_name}')")
                    return await describe_table(table_name)
                # Fallback to list_tables if table name not extracted
                return await list_tables()
                
            elif intent == "Statistics":
                logger.info("Routing query to database_statistics()")
                return await database_statistics()
                
            elif intent == "Relationship":
                logger.info("Routing query to relationship_graph()")
                from database_mcp.tools.metadata import relationship_graph
                return await relationship_graph()
                
            elif intent == "Search":
                # Try to extract LIKE parameter or keyword
                match = re.search(r"LIKE\s+'%?([^'%]+)%?'", sql_clean, re.IGNORECASE)
                keyword = match.group(1) if match else "keyword"
                logger.info(f"Routing query to search_schema('{keyword}')")
                return await search_schema(keyword)
                
            elif intent == "Analytics":
                logger.info("Routing query to analytics_summary()")
                return await analytics_summary()
                
        except Exception as e:
            logger.error(f"Failed to route query internally: {e}", exc_info=True)
            
        return None

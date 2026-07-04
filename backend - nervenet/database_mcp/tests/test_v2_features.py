import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from database_mcp.config import settings
from database_mcp.exceptions import QueryPlanningError
from database_mcp.metadata.cache import metadata_cache, DatabaseMetadata, TableMetadata, ColumnMetadata
from database_mcp.metadata.loader import MetadataLoader, classify_domain, generate_aliases
from database_mcp.services.optimizer import SQLOptimizer
from database_mcp.services.router import IntentRouter
from database_mcp.services.profiler import DatabaseProfiler
from database_mcp.services.metrics import MetricsService, QueryHistoryService
from database_mcp.tools.metadata import database_overview, table_profile, relationship_graph, database_statistics
from database_mcp.tools.sql import analytics_summary

@pytest.fixture
def test_meta_fixture():
    tables = {
        "consumers": TableMetadata(
            name="consumers",
            columns={
                "consumer_id": ColumnMetadata(name="consumer_id", data_type="int", is_nullable=False, is_primary_key=True, is_foreign_key=False),
                "name": ColumnMetadata(name="name", data_type="varchar", is_nullable=True, is_primary_key=False, is_foreign_key=False)
            },
            primary_keys=["consumer_id"],
            row_count=5000,
            data_length=16384,
            index_length=8192,
            update_time="2026-07-03 12:00:00"
        ),
        "bills": TableMetadata(
            name="bills",
            columns={
                "bill_id": ColumnMetadata(name="bill_id", data_type="int", is_nullable=False, is_primary_key=True, is_foreign_key=False),
                "consumer_id": ColumnMetadata(name="consumer_id", data_type="int", is_nullable=False, is_primary_key=False, is_foreign_key=True, foreign_key_target="consumers.consumer_id"),
                "amount": ColumnMetadata(name="amount", data_type="decimal", is_nullable=True, is_primary_key=False, is_foreign_key=False)
            },
            primary_keys=["bill_id"],
            row_count=10000,
            data_length=32768,
            index_length=16384,
            update_time="2026-07-03 13:00:00"
        )
    }
    relationships = [{
        "from_table": "bills",
        "from_column": "consumer_id",
        "to_table": "consumers",
        "to_column": "consumer_id"
    }]
    
    db_meta = DatabaseMetadata(
        database_name="analytics_demo",
        tables=tables,
        relationships=relationships,
        summary="Test Database",
        metadata_version=1,
        schema_version="hash123",
        cache_timestamp="2026-07-03T12:00:00",
        last_refresh="2026-07-03T12:00:00",
        business_domains={"Consumers": ["consumers"], "Billing": ["bills"]}
    )
    metadata_cache.set(db_meta)
    return db_meta

def test_classify_domain():
    """Test table domain classification naming heuristics."""
    assert classify_domain("consumer_master") == "Consumers"
    assert classify_domain("billing_invoice") == "Billing"
    assert classify_domain("meter_readings") == "Meters"
    assert classify_domain("feeder_substation") == "Infrastructure"
    assert classify_domain("solar_kw_generation") == "Energy"
    assert classify_domain("admin_settings") == "Administration"
    assert classify_domain("other_random_table") == "General"

def test_generate_aliases():
    """Test automatic alias generation."""
    aliases = generate_aliases("billing_invoice")
    assert "billing invoice" in aliases
    assert "billing_invoice" in aliases

@pytest.mark.asyncio
async def test_sql_optimizer(test_meta_fixture):
    """Test SQL query optimizer (SELECT * expansion, LIMIT injection)."""
    # 1. Injected LIMIT
    settings.enable_auto_limit = True
    settings.max_rows_returned = 10
    opt_sql = SQLOptimizer.optimize("SELECT * FROM consumers")
    assert "LIMIT 10" in opt_sql
    
    # 2. SELECT * expansion
    expanded = SQLOptimizer.optimize("SELECT * FROM consumers")
    assert "`consumers`.`consumer_id`" in expanded
    assert "`consumers`.`name`" in expanded

def test_intent_router():
    """Test intent classification routing logic."""
    assert IntentRouter.classify_intent("SHOW TABLES") == "Overview"
    assert IntentRouter.classify_intent("DESCRIBE consumers") == "Schema"
    assert IntentRouter.classify_intent("SELECT * FROM consumers") == "Query"
    assert IntentRouter.classify_intent("ANALYTICS_SUMMARY") == "Analytics"

@pytest.mark.asyncio
async def test_query_cost_estimator(test_meta_fixture, mock_cursor):
    """Test query cost estimation rules."""
    from database_mcp.sql.executor import SQLExecutor
    from database_mcp.provider.connection import ConnectionProvider
    
    # Enable cost checking
    settings.query_cost_limit = 1000.0
    
    # Mock EXPLAIN return value with huge row count (e.g. 5000 rows)
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, "SIMPLE", "consumers", None, "ALL", None, None, None, None, 5000, 100.0, "Using where")
    ])
    mock_cursor.description = [("id",), ("select_type",), ("table",), ("partitions",), ("type",), ("possible_keys",), ("key",), ("key_len",), ("ref",), ("rows",), ("filtered",), ("Extra",)]
    
    await ConnectionProvider.initialize()
    
    # Cost (5000) > threshold (1000) -> should raise QueryPlanningError
    with pytest.raises(QueryPlanningError) as exc:
        await SQLExecutor.estimate_cost("SELECT * FROM consumers")
    assert "Query estimated cost" in str(exc.value)

def test_schema_drift_detection(test_meta_fixture):
    """Test schema drift detection comparator."""
    # Create slightly modified metadata version
    tables_new = {
        "consumers": TableMetadata(
            name="consumers",
            columns={
                "consumer_id": ColumnMetadata(name="consumer_id", data_type="int", is_nullable=False, is_primary_key=True, is_foreign_key=False),
                # Column name type changed from varchar to text
                "name": ColumnMetadata(name="name", data_type="text", is_nullable=True, is_primary_key=False, is_foreign_key=False),
                # New column added
                "phone": ColumnMetadata(name="phone", data_type="varchar", is_nullable=True, is_primary_key=False, is_foreign_key=False)
            }
        ),
        # billing table removed, new_table added
        "new_table": TableMetadata(name="new_table", columns={})
    }
    new_meta = DatabaseMetadata(database_name="analytics_demo", tables=tables_new)
    
    drift = MetadataLoader.detect_drift(test_meta_fixture, new_meta)
    
    assert "new_table" in drift["new_tables"]
    assert "bills" in drift["removed_tables"]
    assert "consumers.phone" in drift["new_columns"]
    assert "changed_datatypes" in drift
    assert drift["changed_datatypes"][0]["column"] == "consumers.name"
    assert drift["changed_datatypes"][0]["old_type"] == "varchar"
    assert drift["changed_datatypes"][0]["new_type"] == "text"

@pytest.mark.asyncio
async def test_new_overview_and_stats_tools(test_meta_fixture):
    """Test new database overview, statistics and relationship graph tools."""
    overview_res = await database_overview()
    assert overview_res["success"] is True
    assert overview_res["table_count"] == 2
    assert "Consumers" in overview_res["business_domains"]
    
    stats_res = await database_statistics()
    assert stats_res["success"] is True
    assert stats_res["total_tables"] == 2
    assert stats_res["total_rows"] == 15000
    
    graph_res = await relationship_graph()
    assert graph_res["success"] is True
    assert "consumers" in graph_res["nodes"]
    assert "mermaid_graph" in graph_res

@pytest.mark.asyncio
async def test_analytics_tool(test_meta_fixture, mock_cursor):
    """Test aggregate analytics tool."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[(50000.0, 100.0, 150)])
    mock_cursor.description = [("total_rev",), ("avg_rev",), ("bill_count",)]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    res = await analytics_summary()
    assert res["success"] is True
    analytics = res["analytics_summary"]
    assert "billing_revenue_summary" in analytics
    assert analytics["billing_revenue_summary"]["total_revenue"] == 50000.0
    assert analytics["billing_revenue_summary"]["total_bills_issued"] == 150

@pytest.mark.asyncio
async def test_table_profiler_fallback(test_meta_fixture):
    """Test profiler logic with mock DB response fallback."""
    # Directly profile table
    profile = await DatabaseProfiler.profile_table("consumers", force_refresh=True)
    assert profile["table_name"] == "consumers"
    assert profile["row_count"] == 5000
    assert len(profile["columns"]) == 2

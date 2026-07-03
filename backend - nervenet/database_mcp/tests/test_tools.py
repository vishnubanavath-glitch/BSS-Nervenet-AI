import pytest
from unittest.mock import AsyncMock, patch
from database_mcp.metadata.cache import metadata_cache, DatabaseMetadata, TableMetadata, ColumnMetadata
from database_mcp.tools.metadata import discover_database, list_tables, describe_table, list_relationships, search_schema
from database_mcp.tools.sql import validate_sql, execute_sql, explain_sql
from database_mcp.tools.utility import health_check, refresh_metadata

@pytest.fixture
def populated_metadata():
    """Warms cache with mock database metadata."""
    tables = {
        "consumers": TableMetadata(
            name="consumers",
            columns={
                "consumer_id": ColumnMetadata(name="consumer_id", data_type="int", is_nullable=False, is_primary_key=True, is_foreign_key=False),
                "name": ColumnMetadata(name="name", data_type="varchar", is_nullable=True, is_primary_key=False, is_foreign_key=False)
            },
            primary_keys=["consumer_id"],
            foreign_keys=[]
        ),
        "bills": TableMetadata(
            name="bills",
            columns={
                "bill_id": ColumnMetadata(name="bill_id", data_type="int", is_nullable=False, is_primary_key=True, is_foreign_key=False),
                "consumer_id": ColumnMetadata(name="consumer_id", data_type="int", is_nullable=False, is_primary_key=False, is_foreign_key=True, foreign_key_target="consumers.consumer_id")
            },
            primary_keys=["bill_id"],
            foreign_keys=[{"column": "consumer_id", "referenced_table": "consumers", "referenced_column": "consumer_id"}]
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
        summary="Database 'analytics_demo' contains 2 tables: consumers, bills."
    )
    metadata_cache.set(db_meta)
    return db_meta

@pytest.mark.asyncio
async def test_discover_database_tool(populated_metadata):
    """Test discover_database metadata tool."""
    res = await discover_database()
    assert res["success"] is True
    assert res["database_name"] == "analytics_demo"
    assert res["table_count"] == 2
    assert "consumers, bills" in res["summary"]

@pytest.mark.asyncio
async def test_list_tables_tool(populated_metadata):
    """Test list_tables metadata tool."""
    res = await list_tables()
    assert res["success"] is True
    assert sorted(res["tables"]) == ["bills", "consumers"]

@pytest.mark.asyncio
async def test_describe_table_tool(populated_metadata):
    """Test describe_table metadata tool."""
    # Valid table
    res = await describe_table("consumers")
    assert res["success"] is True
    assert res["table"] == "consumers"
    assert "consumer_id" in res["columns"]
    assert res["primary_keys"] == ["consumer_id"]
    
    # Invalid table
    res_err = await describe_table("non_existent")
    assert res_err["success"] is False
    assert res_err["error"]["code"] == "METADATA_ERROR"

@pytest.mark.asyncio
async def test_list_relationships_tool(populated_metadata):
    """Test list_relationships metadata tool."""
    res = await list_relationships()
    assert res["success"] is True
    assert len(res["relationships"]) == 1
    assert res["relationships"][0]["from_table"] == "bills"

@pytest.mark.asyncio
async def test_search_schema_tool(populated_metadata):
    """Test search_schema metadata tool."""
    res = await search_schema("consumer")
    assert res["success"] is True
    assert res["matching_tables"] == ["consumers"]
    assert "consumers.consumer_id" in res["matching_columns"]

@pytest.mark.asyncio
async def test_validate_sql_tool():
    """Test validate_sql security tool."""
    # Valid
    res = await validate_sql("SELECT * FROM bills")
    assert res["success"] is True
    
    # Invalid
    res_err = await validate_sql("DROP TABLE bills")
    assert res_err["success"] is False
    assert res_err["error"]["code"] == "SQL_VALIDATION_ERROR"

@pytest.mark.asyncio
async def test_execute_sql_tool(mock_cursor):
    """Test execute_sql tool runs and intercepts driver errors."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[(100,)])
    mock_cursor.description = [("total",)]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    res = await execute_sql("SELECT count(*) FROM bills")
    assert res["success"] is True
    assert res["columns"] == ["total"]
    assert res["rows"] == [[100]]

@pytest.mark.asyncio
async def test_explain_sql_tool(mock_cursor):
    """Test explain_sql tool returns plain English and query execution plan."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, "SIMPLE", "consumers", None, "ALL", None, None, None, 10, 100.0, "Using where")
    ])
    mock_cursor.description = [
        ("id",), ("select_type",), ("table",), ("partitions",), ("type",), 
        ("possible_keys",), ("key",), ("key_len",), ("ref",), ("rows",), 
        ("filtered",), ("Extra",)
    ]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    res = await explain_sql("SELECT * FROM consumers WHERE id = 5")
    assert res["success"] is True
    assert "consumers" in res["plain_english_explanation"]
    assert len(res["mysql_execution_plan"]) == 1
    assert res["mysql_execution_plan"][0]["table"] == "consumers"

@pytest.mark.asyncio
async def test_health_check_tool(populated_metadata, mock_cursor):
    """Test health_check tool."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[(1,)])
    mock_cursor.description = [("1",)]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    res = await health_check()
    assert res["success"] is True
    assert res["status"] == "healthy"
    assert res["components"]["database"]["status"] == "healthy"
    assert res["components"]["metadata_cache"]["status"] == "healthy"

@pytest.mark.asyncio
async def test_refresh_metadata_tool(populated_metadata, mock_cursor):
    """Test refresh_metadata clears and reloads the cache."""
    # Mock INFORMATION_SCHEMA response
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock()
    mock_cursor.fetchall.side_effect = [
        [("consumers", "id", "int", "NO", "PRI")], # Columns
        []                                          # Constraints
    ]
    mock_cursor.description = [("placeholder",)]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    res = await refresh_metadata()
    assert res["success"] is True
    assert res["table_count"] == 1
    assert "consumers" in metadata_cache.get().tables

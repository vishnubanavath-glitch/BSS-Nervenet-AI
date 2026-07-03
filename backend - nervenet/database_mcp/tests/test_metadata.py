import pytest
from unittest.mock import patch, AsyncMock
from database_mcp.metadata.cache import metadata_cache, DatabaseMetadata, TableMetadata, ColumnMetadata
from database_mcp.metadata.loader import MetadataLoader
from database_mcp.exceptions import MetadataError

def test_metadata_cache():
    """Test manual metadata cache methods."""
    assert not metadata_cache.is_warmed()
    assert metadata_cache.get() is None
    
    dummy_meta = DatabaseMetadata(
        database_name="analytics_demo",
        tables={},
        relationships=[]
    )
    
    metadata_cache.set(dummy_meta)
    assert metadata_cache.is_warmed()
    assert metadata_cache.get() is dummy_meta
    
    metadata_cache.clear()
    assert not metadata_cache.is_warmed()
    assert metadata_cache.get() is None

@pytest.mark.asyncio
async def test_loader_success(mock_cursor):
    """Test loader successfully fetches columns, primary/foreign keys, and builds relationships."""
    # 1. Mock first execute query for Columns information:
    # TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
    mock_columns_rows = [
        ("consumers", "consumer_id", "int", "NO", "PRI"),
        ("consumers", "name", "varchar", "YES", ""),
        ("consumers", "email", "varchar", "YES", ""),
        ("bills", "bill_id", "int", "NO", "PRI"),
        ("bills", "consumer_id", "int", "NO", ""),
        ("bills", "amount", "decimal", "YES", ""),
    ]
    
    # 2. Mock second execute query for Constraints / Foreign Keys information:
    # TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    mock_keys_rows = [
        ("bills", "consumer_id", "fk_bills_consumers", "consumers", "consumer_id")
    ]
    
    # Configure the cursor execute mock sequences
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock()
    mock_cursor.fetchall.side_effect = [
        mock_columns_rows,  # First query fetch
        mock_keys_rows      # Second query fetch
    ]
    mock_cursor.description = [("col_placeholder",)] # Dummy to prevent error

    # Setup database pool
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()

    # Load and cache
    db_meta = await MetadataLoader.load_and_cache()
    
    # Verify loaded cache
    assert metadata_cache.is_warmed()
    assert db_meta.database_name == "analytics_demo"
    assert "consumers" in db_meta.tables
    assert "bills" in db_meta.tables
    
    # Test consumers columns
    consumers_tbl = db_meta.tables["consumers"]
    assert len(consumers_tbl.columns) == 3
    assert consumers_tbl.columns["consumer_id"].is_primary_key
    assert not consumers_tbl.columns["consumer_id"].is_foreign_key
    assert consumers_tbl.primary_keys == ["consumer_id"]
    
    # Test bills columns and relationships
    bills_tbl = db_meta.tables["bills"]
    assert len(bills_tbl.columns) == 3
    assert bills_tbl.columns["bill_id"].is_primary_key
    assert bills_tbl.columns["consumer_id"].is_foreign_key
    assert bills_tbl.columns["consumer_id"].foreign_key_target == "consumers.consumer_id"
    
    assert len(db_meta.relationships) == 1
    assert db_meta.relationships[0]["from_table"] == "bills"
    assert db_meta.relationships[0]["from_column"] == "consumer_id"
    assert db_meta.relationships[0]["to_table"] == "consumers"
    assert db_meta.relationships[0]["to_column"] == "consumer_id"

@pytest.mark.asyncio
async def test_loader_failure(mock_cursor):
    """Test loader handles database failure gracefully."""
    mock_cursor.execute.side_effect = Exception("DB Connection Lost")
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    with pytest.raises(MetadataError) as exc_info:
        await MetadataLoader.load_and_cache()
        
    assert "Failed to load schema metadata from MySQL" in str(exc_info.value)
    assert not metadata_cache.is_warmed()

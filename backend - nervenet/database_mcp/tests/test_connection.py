import pytest
from unittest.mock import AsyncMock
from database_mcp.provider.connection import ConnectionProvider
from database_mcp.exceptions import ConnectionError
import asyncmy

@pytest.mark.asyncio
async def test_initialize_pool(mock_create_pool, mock_pool):
    """Test that connection pool initializes once and correctly."""
    assert ConnectionProvider._pool is None
    
    await ConnectionProvider.initialize()
    
    assert ConnectionProvider._pool is mock_pool
    mock_create_pool.assert_called_once()
    
    # Second call should be a no-op
    await ConnectionProvider.initialize()
    mock_create_pool.assert_called_once()

@pytest.mark.asyncio
async def test_close_pool(mock_pool):
    """Test that pool closing executes successfully."""
    await ConnectionProvider.initialize()
    assert ConnectionProvider._pool is mock_pool
    
    await ConnectionProvider.close()
    
    assert ConnectionProvider._pool is None
    mock_pool.close.assert_called_once()
    mock_pool.wait_closed.assert_called_once()

@pytest.mark.asyncio
async def test_acquire_connection(mock_pool, mock_connection):
    """Test connection acquisition context manager."""
    await ConnectionProvider.initialize()
    
    async with ConnectionProvider.acquire() as conn:
        assert conn is mock_connection
        
    mock_pool.acquire.assert_called_once()

@pytest.mark.asyncio
async def test_initialize_failure(mock_create_pool):
    """Test connection initialization failure behavior."""
    mock_create_pool.side_effect = Exception("MySQL Refused connection")
    
    with pytest.raises(ConnectionError) as exc_info:
        await ConnectionProvider.initialize()
        
    assert "Failed to establish database connection pool" in str(exc_info.value)

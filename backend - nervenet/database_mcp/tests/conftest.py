import pytest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture(autouse=True)
def mock_db_settings(monkeypatch):
    """Set env variables for test configuration."""
    from database_mcp.config import settings
    settings.db_host = "localhost"
    settings.db_port = 3306
    settings.db_user = "test_user"
    settings.db_password = "test_pass"
    settings.db_name = "analytics_demo"
    settings.query_cost_limit = 0.0
    settings.enable_auto_limit = False

@pytest.fixture
def mock_cursor():
    """Mock database cursor."""
    cursor = MagicMock()
    cursor.execute = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    
    async def mock_fetchmany(size=None):
        return await cursor.fetchall()
        
    cursor.fetchmany = AsyncMock(side_effect=mock_fetchmany)
    cursor.description = None
    return cursor

@pytest.fixture
def mock_connection(mock_cursor):
    """Mock connection yielding the mock cursor."""
    conn = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock()
    return conn

@pytest.fixture
def mock_pool(mock_connection):
    """Mock connection pool yielding the mock connection."""
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
    pool.acquire.return_value.__aexit__ = AsyncMock()
    pool.close = MagicMock()
    pool.wait_closed = AsyncMock()
    return pool

@pytest.fixture(autouse=True)
def mock_create_pool(mock_pool):
    """Mock asyncmy.create_pool to return the mock pool."""
    with unittest.mock.patch("asyncmy.create_pool", new_callable=AsyncMock) as m:
        m.return_value = mock_pool
        yield m

@pytest.fixture(autouse=True)
def clear_state():
    """Clear singleton states of connection provider and cache between runs."""
    from database_mcp.provider.connection import ConnectionProvider
    from database_mcp.metadata.cache import metadata_cache
    ConnectionProvider._pool = None
    metadata_cache.clear()
    yield
    ConnectionProvider._pool = None
    metadata_cache.clear()

import pytest
from database_mcp.sql.validator import SQLValidator
from database_mcp.sql.executor import SQLExecutor
from database_mcp.exceptions import SqlValidationError, SqlExecutionError
from unittest.mock import AsyncMock

def test_sql_validator_allowed():
    """Test allowed read-only statements."""
    allowed_queries = [
        "SELECT * FROM consumers",
        "select id, name from consumers where active = 1",
        "WITH active_users AS (SELECT * FROM users) SELECT * FROM active_users",
        "SHOW TABLES",
        "DESCRIBE bills",
        "EXPLAIN SELECT * FROM readings",
        "SELECT * FROM logs -- comment containing DELETE keyword",
        "SELECT * FROM orders WHERE status = 'UPDATE'", # Forbidden keyword in string literal
        "SELECT id /* comment */ FROM users"
    ]
    for q in allowed_queries:
        # Should execute without throwing exception
        SQLValidator.validate(q)

def test_sql_validator_forbidden():
    """Test forbidden statements are correctly rejected."""
    forbidden_queries = [
        "INSERT INTO consumers (name) VALUES ('John')",
        "UPDATE consumers SET name = 'Bob'",
        "DELETE FROM bills WHERE id = 10",
        "DROP TABLE users",
        "ALTER TABLE readings ADD COLUMN notes VARCHAR(255)",
        "CREATE TABLE test (id INT)",
        "TRUNCATE TABLE logs",
        "GRANT ALL PRIVILEGES ON *.* TO 'malicious'",
        "REVOKE ALL ON db FROM 'user'",
        # Multi-statement injection attempts
        "SELECT * FROM consumers; DROP TABLE bills;",
        "SELECT * FROM consumers; DELETE FROM bills",
        # Case insensitivity checks
        "DeLeTe from bills",
        "insert into bills values (1)"
    ]
    for q in forbidden_queries:
        with pytest.raises(SqlValidationError) as exc_info:
            SQLValidator.validate(q)
        assert "Forbidden SQL" in str(exc_info.value) or "statement type" in str(exc_info.value)

@pytest.mark.asyncio
async def test_executor_success(mock_cursor):
    """Test SQLExecutor runs successfully and returns formatted results."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        (1, "Alice", "alice@example.com"),
        (2, "Bob", "bob@example.com")
    ])
    mock_cursor.description = [("id",), ("name",), ("email",)]

    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()

    result = await SQLExecutor.execute("SELECT id, name, email FROM consumers")
    
    assert result["success"] is True
    assert result["columns"] == ["id", "name", "email"]
    assert len(result["rows"]) == 2
    assert result["rows"][0] == [1, "Alice", "alice@example.com"]
    assert result["row_count"] == 2
    assert isinstance(result["execution_time_ms"], float)
    assert result["execution_time_ms"] >= 0

@pytest.mark.asyncio
async def test_executor_limit(mock_cursor):
    """Test that max_rows forces fetchmany call rather than fetchall."""
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchmany = AsyncMock(return_value=[(1, "Alice")])
    mock_cursor.description = [("id",), ("name",)]

    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()

    result = await SQLExecutor.execute("SELECT id, name FROM consumers", max_rows=5)
    
    assert result["row_count"] == 1
    mock_cursor.fetchmany.assert_called_once_with(5)
    mock_cursor.fetchall.assert_not_called()

import pytest
import datetime
import decimal
from unittest.mock import AsyncMock, patch
from database_mcp.sql.analytics import (
    determine_sampling_method,
    strip_outer_limit,
    detect_column_types,
    compute_python_stats,
    build_sql_stats_query,
    build_sql_duplicate_query,
    merge_stats
)
from database_mcp.sql.executor import SQLExecutor
from database_mcp.provider.connection import ConnectionProvider

def test_sampling_method_inference():
    assert determine_sampling_method("SELECT * FROM t") == "first_n_rows"
    assert determine_sampling_method("SELECT * FROM t ORDER BY col") == "ordered_sample"
    assert determine_sampling_method("SELECT * FROM t ORDER BY RAND()") == "random_sample"

def test_strip_outer_limit():
    assert strip_outer_limit("SELECT * FROM t LIMIT 10") == "SELECT * FROM t"
    assert strip_outer_limit("SELECT * FROM t LIMIT 10 OFFSET 5") == "SELECT * FROM t"
    assert strip_outer_limit("SELECT * FROM t limit 10;") == "SELECT * FROM t"
    assert strip_outer_limit("SELECT * FROM t LIMIT 5, 10") == "SELECT * FROM t"
    assert strip_outer_limit("SELECT * FROM t -- comment\nLIMIT 10") == "SELECT * FROM t"

def test_column_type_detection():
    cols = ["c_num", "c_cat", "c_date", "c_bool"]
    rows = [
        [10.5, "active", datetime.date(2026, 1, 1), True],
        [20.0, "inactive", datetime.date(2026, 1, 2), False],
        [None, None, None, None]
    ]
    types = detect_column_types(cols, rows)
    assert types["c_num"] == "numeric"
    assert types["c_cat"] == "categorical"
    assert types["c_date"] == "date"
    assert types["c_bool"] == "boolean"

def test_compute_python_stats():
    cols = ["num", "cat", "bool"]
    rows = [[10, "A", True], [20, "B", False], [30, "A", True]]
    col_types = {"num": "numeric", "cat": "categorical", "bool": "boolean"}
    
    res = compute_python_stats(cols, rows, col_types)
    stats = res["stats"]
    dq = res["data_quality_cols"]
    
    assert stats["num"]["minimum"] == 10
    assert stats["num"]["maximum"] == 30
    assert stats["num"]["average"] == 20
    assert stats["num"]["median"] == 20
    assert stats["num"]["percentile_25"] == 15.0
    assert stats["num"]["percentile_75"] == 25.0
    
    assert stats["cat"]["distinct_count"] == 2
    assert stats["cat"]["top_values"] == ["A", "B"]
    
    assert stats["bool"]["true_count"] == 2
    assert stats["bool"]["false_count"] == 1

def test_build_sql_stats_query():
    col_types = {"num": "numeric", "cat": "categorical"}
    sql = build_sql_stats_query("SELECT num, cat FROM t", ["num", "cat"], col_types)
    assert "MIN(`num`)" in sql
    assert "COUNT(DISTINCT `cat`)" in sql

@pytest.mark.asyncio
async def test_executor_with_analytics_small(mock_cursor):
    # Returns 5 rows, should NOT compute stats because rows <= 100
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        [1, "A"], [2, "B"], [3, "A"], [4, "B"], [5, "A"]
    ])
    mock_cursor.description = [("id",), ("name",)]
    
    await ConnectionProvider.initialize()
    
    res = await SQLExecutor.execute("SELECT id, name FROM table", max_rows=100)
    assert res["success"] is True
    assert "execution" in res
    assert res["execution"]["total_matching_rows"] == 5
    assert "statistical_summary" not in res
    assert "data_quality" not in res
    assert "database_time_ms" in res["execution"]
    assert "total_time_ms" in res["execution"]

@pytest.mark.asyncio
async def test_executor_with_analytics_medium(mock_cursor):
    # Returns 150 rows, should compute stats because rows > 100
    rows = [[i, "A" if i % 2 == 0 else "B"] for i in range(1, 151)]
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)
    mock_cursor.description = [("id",), ("name",)]
    
    await ConnectionProvider.initialize()
    
    res = await SQLExecutor.execute("SELECT id, name FROM table", max_rows=200)
    assert res["success"] is True
    assert "execution" in res
    assert res["execution"]["total_matching_rows"] == 150
    assert "statistical_summary" in res
    assert "data_quality" in res
    assert res["statistical_summary"]["id"]["minimum"] == 1
    assert res["statistical_summary"]["id"]["maximum"] == 150
    assert res["data_quality"]["duplicate_rows"] == 0

def test_count_joins_in_sql():
    from database_mcp.sql.analytics import count_joins_in_sql
    
    # Standard joins
    assert count_joins_in_sql("SELECT * FROM a JOIN b ON a.id = b.id") == 1
    assert count_joins_in_sql("SELECT * FROM a LEFT JOIN b ON a.id = b.id JOIN c ON b.id = c.id") == 2
    assert count_joins_in_sql("SELECT * FROM a FULL JOIN b") == 1
    
    # Unions (should be 0)
    assert count_joins_in_sql("SELECT * FROM a UNION SELECT * FROM b") == 0
    assert count_joins_in_sql("SELECT * FROM a UNION ALL SELECT * FROM b") == 0
    
    # String literal / comment matching (should be 0)
    assert count_joins_in_sql("SELECT * FROM a WHERE name = 'JOIN'") == 0
    assert count_joins_in_sql("SELECT * FROM a -- JOIN comments here\nWHERE id = 1") == 0

def test_get_simple_table_name_if_no_filters():
    from database_mcp.sql.analytics import get_simple_table_name_if_no_filters
    
    assert get_simple_table_name_if_no_filters("SELECT * FROM consumers") == "consumers"
    assert get_simple_table_name_if_no_filters("SELECT id, name FROM bills LIMIT 1000") == "bills"
    assert get_simple_table_name_if_no_filters("SELECT * FROM `payment_transactions` LIMIT 10 OFFSET 5;") == "payment_transactions"
    
    # Queries with filters or joins should return None
    assert get_simple_table_name_if_no_filters("SELECT * FROM consumers WHERE id = 1") is None
    assert get_simple_table_name_if_no_filters("SELECT * FROM consumers JOIN bills") is None
    assert get_simple_table_name_if_no_filters("SELECT COUNT(*) FROM consumers") is None
    assert get_simple_table_name_if_no_filters("SELECT * FROM a UNION SELECT * FROM b") is None


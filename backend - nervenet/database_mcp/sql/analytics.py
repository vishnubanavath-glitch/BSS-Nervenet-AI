import re
import math
import decimal
import datetime
import collections
import sqlparse
from typing import List, Dict, Any, Optional, Tuple

def determine_sampling_method(sql: str) -> str:
    """Infers the sampling method from the SQL query string."""
    sql_upper = sql.upper()
    if "RAND(" in sql_upper:
        return "random_sample"
    elif "ORDER BY" in sql_upper:
        return "ordered_sample"
    else:
        return "first_n_rows"

def strip_outer_limit(sql: str) -> str:
    """Cleans comments and strips the outermost LIMIT and OFFSET clauses from a SELECT query."""
    # Strip comments and clean up formatting
    cleaned_sql = sqlparse.format(sql, strip_comments=True).strip()
    cleaned_sql_rstrip = cleaned_sql.rstrip(';')
    
    # Matches: LIMIT <count> [OFFSET <offset>] or LIMIT <offset>, <count>
    pattern = re.compile(r'\bLIMIT\s+\d+(?:\s+OFFSET\s+\d+)?\s*$', re.IGNORECASE)
    pattern_comma = re.compile(r'\bLIMIT\s+\d+\s*,\s+\d+\s*$', re.IGNORECASE)
    
    if pattern.search(cleaned_sql_rstrip):
        return pattern.sub('', cleaned_sql_rstrip).strip()
    elif pattern_comma.search(cleaned_sql_rstrip):
        return pattern_comma.sub('', cleaned_sql_rstrip).strip()
        
    return cleaned_sql_rstrip

def detect_column_types(columns: List[str], rows: List[List[Any]]) -> Dict[str, str]:
    """Classifies each column into numeric, boolean, date, categorical, or unknown based on data types."""
    col_types = {}
    if not rows:
        for col in columns:
            col_types[col] = "unknown"
        return col_types

    for i, col_name in enumerate(columns):
        vals = [row[i] for row in rows if row[i] is not None]
        if not vals:
            col_types[col_name] = "unknown"
            continue

        # Check types (bool must come first because isinstance(True, int) is True)
        if all(isinstance(v, bool) for v in vals):
            col_types[col_name] = "boolean"
            continue

        if all(isinstance(v, (int, float, decimal.Decimal)) for v in vals):
            col_types[col_name] = "numeric"
            continue

        if all(isinstance(v, (datetime.datetime, datetime.date)) for v in vals):
            col_types[col_name] = "date"
            continue

        # Fallback to categorical
        col_types[col_name] = "categorical"

    return col_types

def safe_float(val: Any) -> Optional[float]:
    """Converts a value to float if possible, returning None otherwise."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_int(val: Any) -> Optional[int]:
    """Converts a value to int if possible, returning None otherwise."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def compute_python_stats(columns: List[str], rows: List[List[Any]], col_types: Dict[str, str]) -> Dict[str, Any]:
    """Computes exact statistics and data quality metrics for columns using Python."""
    stats = {}
    data_quality_cols = {}
    total_rows = len(rows)

    has_numeric = any(t == "numeric" for t in col_types.values())
    has_categorical = any(t == "categorical" for t in col_types.values())

    for i, col_name in enumerate(columns):
        col_type = col_types.get(col_name, "unknown")
        vals = [row[i] for row in rows if row[i] is not None]
        null_count = total_rows - len(vals)
        null_percentage = (null_count / total_rows * 100) if total_rows > 0 else 0.0

        # Data quality entry
        data_quality_cols[col_name] = {
            "null_count": null_count,
            "null_percentage": round(null_percentage, 2)
        }

        if col_type == "unknown" or not vals:
            continue

        if col_type == "numeric":
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            
            # Median
            if n % 2 == 1:
                median = float(sorted_vals[n // 2])
            else:
                median = float(sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

            # Average
            avg = float(sum(vals) / n)

            # Variance & Stddev
            variance = float(sum((x - avg) ** 2 for x in vals) / n)
            std_dev = math.sqrt(variance)

            # Percentiles
            def get_percentile(p: float) -> float:
                k = (n - 1) * (p / 100.0)
                f = math.floor(k)
                c = math.ceil(k)
                if f == c:
                    return float(sorted_vals[int(k)])
                return float(sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f]))

            p25 = get_percentile(25.0)
            p75 = get_percentile(75.0)
            p95 = get_percentile(95.0)

            # Mode (only compute if numeric columns exist and it is reasonable)
            counter = collections.Counter(vals)
            mode_val, mode_count = counter.most_common(1)[0]
            mode = float(mode_val) if (mode_count > 1 or len(counter) == 1) else None

            stats[col_name] = {
                "type": "numeric",
                "minimum": float(min(vals)),
                "maximum": float(max(vals)),
                "average": round(avg, 4),
                "median": round(median, 4),
                "mode": round(mode, 4) if mode is not None else None,
                "standard_deviation": round(std_dev, 4),
                "variance": round(variance, 4),
                "percentile_25": round(p25, 4),
                "percentile_75": round(p75, 4),
                "percentile_95": round(p95, 4),
                "distinct_count": len(set(vals)),
                "null_count": null_count
            }

        elif col_type == "categorical":
            empty_string_count = sum(1 for v in vals if isinstance(v, str) and v == "")
            data_quality_cols[col_name]["empty_string_count"] = empty_string_count

            counter = collections.Counter(vals)
            freq_dist = {str(k): v for k, v in counter.most_common(10)}
            top_vals = list(freq_dist.keys())

            stats[col_name] = {
                "type": "categorical",
                "distinct_count": len(set(vals))
            }
            # Skip top values and frequency if no categorical exist (handled by filter)
            if has_categorical:
                stats[col_name]["top_values"] = top_vals
                stats[col_name]["frequency_distribution"] = freq_dist

        elif col_type == "date":
            min_date = min(vals)
            max_date = max(vals)
            min_date_str = min_date.isoformat() if hasattr(min_date, "isoformat") else str(min_date)
            max_date_str = max_date.isoformat() if hasattr(max_date, "isoformat") else str(max_date)

            try:
                d1 = min_date.date() if isinstance(min_date, datetime.datetime) else min_date
                d2 = max_date.date() if isinstance(max_date, datetime.datetime) else max_date
                delta = d2 - d1
                date_range_str = f"{delta.days} days"
            except Exception:
                date_range_str = "unknown"

            stats[col_name] = {
                "type": "date",
                "minimum_date": min_date_str,
                "maximum_date": max_date_str,
                "unique_dates": len(set(vals)),
                "date_range": date_range_str
            }

        elif col_type == "boolean":
            true_count = sum(1 for v in vals if v is True or v == 1)
            false_count = sum(1 for v in vals if v is False or v == 0)

            stats[col_name] = {
                "type": "boolean",
                "true_count": true_count,
                "false_count": false_count,
                "null_count": null_count
            }

    return {"stats": stats, "data_quality_cols": data_quality_cols}

def build_sql_stats_query(sql_without_limit: str, columns: List[str], col_types: Dict[str, str]) -> str:
    """Creates a SQL query to compute column statistics on the database side."""
    select_exprs = []
    for i, col_name in enumerate(columns):
        col_type = col_types.get(col_name, "unknown")
        q = f"`{col_name.replace('`', '``')}`"
        
        if col_type == "numeric":
            select_exprs.extend([
                f"MIN({q}) AS num_min_{i}",
                f"MAX({q}) AS num_max_{i}",
                f"AVG({q}) AS num_avg_{i}",
                f"STDDEV({q}) AS num_std_{i}",
                f"VARIANCE({q}) AS num_var_{i}",
                f"COUNT(DISTINCT {q}) AS num_dist_{i}",
                f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS num_null_{i}"
            ])
        elif col_type == "categorical":
            select_exprs.extend([
                f"COUNT(DISTINCT {q}) AS cat_dist_{i}",
                f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS cat_null_{i}",
                f"SUM(CASE WHEN {q} = '' THEN 1 ELSE 0 END) AS cat_empty_{i}"
            ])
        elif col_type == "date":
            select_exprs.extend([
                f"MIN({q}) AS date_min_{i}",
                f"MAX({q}) AS date_max_{i}",
                f"COUNT(DISTINCT {q}) AS date_dist_{i}",
                f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS date_null_{i}"
            ])
        elif col_type == "boolean":
            select_exprs.extend([
                f"SUM(CASE WHEN {q} = 1 THEN 1 ELSE 0 END) AS bool_true_{i}",
                f"SUM(CASE WHEN {q} = 0 THEN 1 ELSE 0 END) AS bool_false_{i}",
                f"SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) AS bool_null_{i}"
            ])

    if not select_exprs:
        select_exprs = ["1 AS dummy"]

    select_clause = ", ".join(select_exprs)
    return f"SELECT {select_clause} FROM ({sql_without_limit}) AS sub_stats"

def build_sql_duplicate_query(sql_without_limit: str, columns: List[str]) -> str:
    """Builds a group-by count query to calculate duplicate rows on the database side."""
    quoted_cols = ", ".join(f"`{col.replace('`', '``')}`" for col in columns)
    return f"SELECT SUM(cnt - 1) AS duplicate_rows FROM (SELECT COUNT(*) as cnt FROM ({sql_without_limit}) AS sub_dup GROUP BY {quoted_cols} HAVING COUNT(*) > 1) AS dups"

def merge_stats(
    db_stats_row: Dict[str, Any],
    python_sample_stats: Dict[str, Any],
    columns: List[str],
    col_types: Dict[str, str],
    total_rows: int
) -> Dict[str, Any]:
    """Merges database-side stats with Python sample stats (percentiles, median, frequency distributions)."""
    stats = {}
    data_quality_cols = {}

    has_numeric = any(t == "numeric" for t in col_types.values())
    has_categorical = any(t == "categorical" for t in col_types.values())

    for i, col_name in enumerate(columns):
        col_type = col_types.get(col_name, "unknown")
        
        # Extract null count
        null_count = 0
        if col_type == "numeric":
            null_count = db_stats_row.get(f"num_null_{i}")
        elif col_type == "categorical":
            null_count = db_stats_row.get(f"cat_null_{i}")
        elif col_type == "date":
            null_count = db_stats_row.get(f"date_null_{i}")
        elif col_type == "boolean":
            null_count = db_stats_row.get(f"bool_null_{i}")
            
        null_count = safe_int(null_count) or 0
        null_percentage = (null_count / total_rows * 100) if total_rows > 0 else 0.0
        
        data_quality_cols[col_name] = {
            "null_count": null_count,
            "null_percentage": round(null_percentage, 2)
        }

        sample_col_stats = python_sample_stats.get("stats", {}).get(col_name, {})

        if col_type == "numeric":
            min_val = safe_float(db_stats_row.get(f"num_min_{i}"))
            max_val = safe_float(db_stats_row.get(f"num_max_{i}"))
            avg_val = safe_float(db_stats_row.get(f"num_avg_{i}"))
            std_val = safe_float(db_stats_row.get(f"num_std_{i}"))
            var_val = safe_float(db_stats_row.get(f"num_var_{i}"))
            dist_val = safe_int(db_stats_row.get(f"num_dist_{i}")) or 0

            stats[col_name] = {
                "type": "numeric",
                "minimum": min_val,
                "maximum": max_val,
                "average": round(avg_val, 4) if avg_val is not None else None,
                "median": sample_col_stats.get("median"),
                "mode": sample_col_stats.get("mode"),
                "standard_deviation": round(std_val, 4) if std_val is not None else None,
                "variance": round(var_val, 4) if var_val is not None else None,
                "percentile_25": sample_col_stats.get("percentile_25"),
                "percentile_75": sample_col_stats.get("percentile_75"),
                "percentile_95": sample_col_stats.get("percentile_95"),
                "distinct_count": dist_val,
                "null_count": null_count
            }

        elif col_type == "categorical":
            dist_val = safe_int(db_stats_row.get(f"cat_dist_{i}")) or 0
            empty_val = safe_int(db_stats_row.get(f"cat_empty_{i}"))
            if empty_val is not None:
                data_quality_cols[col_name]["empty_string_count"] = empty_val

            stats[col_name] = {
                "type": "categorical",
                "distinct_count": dist_val
            }
            if has_categorical:
                stats[col_name]["top_values"] = sample_col_stats.get("top_values", []),
                stats[col_name]["frequency_distribution"] = sample_col_stats.get("frequency_distribution", {})

        elif col_type == "date":
            min_date = db_stats_row.get(f"date_min_{i}")
            max_date = db_stats_row.get(f"date_max_{i}")
            dist_val = safe_int(db_stats_row.get(f"date_dist_{i}")) or 0
            
            min_date_str = min_date.isoformat() if hasattr(min_date, "isoformat") else (str(min_date) if min_date is not None else None)
            max_date_str = max_date.isoformat() if hasattr(max_date, "isoformat") else (str(max_date) if max_date is not None else None)

            date_range_str = "unknown"
            if min_date is not None and max_date is not None:
                try:
                    d1 = min_date.date() if isinstance(min_date, datetime.datetime) else min_date
                    d2 = max_date.date() if isinstance(max_date, datetime.datetime) else max_date
                    delta = d2 - d1
                    date_range_str = f"{delta.days} days"
                except Exception:
                    pass

            stats[col_name] = {
                "type": "date",
                "minimum_date": min_date_str,
                "maximum_date": max_date_str,
                "unique_dates": dist_val,
                "date_range": date_range_str
            }

        elif col_type == "boolean":
            true_val = safe_int(db_stats_row.get(f"bool_true_{i}")) or 0
            false_val = safe_int(db_stats_row.get(f"bool_false_{i}")) or 0

            stats[col_name] = {
                "type": "boolean",
                "true_count": true_val,
                "false_count": false_val,
                "null_count": null_count
            }

    return {"stats": stats, "data_quality_cols": data_quality_cols}

def count_joins_in_sql(sql: str) -> int:
    """Traverses parsed SQL tokens to count actual JOIN keywords while ignoring UNION/UNION ALL keywords, comments, and string literals."""
    try:
        cleaned = sqlparse.format(sql, strip_comments=True)
        parsed = sqlparse.parse(cleaned)
        if not parsed:
            return 0
        
        join_count = 0
        
        def traverse(token_list):
            nonlocal join_count
            for token in token_list:
                if token.is_group:
                    traverse(token.tokens)
                else:
                    val = str(token.value).upper().strip()
                    if token.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML) or token.ttype is None:
                        if val in ("JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN", "OUTER JOIN"):
                            join_count += 1
        
        traverse(parsed[0].tokens)
        return join_count
    except Exception:
        try:
            cleaned = sqlparse.format(sql, strip_comments=True)
            cleaned_no_str = re.sub(r"'[^']*'", "", cleaned)
            cleaned_no_str = re.sub(r'"[^"]*"', "", cleaned_no_str)
            joins = re.findall(r'\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+|CROSS\s+)?JOIN\b', cleaned_no_str, re.IGNORECASE)
            return len(joins)
        except Exception:
            return 0

def get_simple_table_name_if_no_filters(sql: str) -> Optional[str]:
    """If the query is a simple SELECT from a single table with no filters (no WHERE, JOIN, GROUP BY, HAVING, UNION, etc.), returns the table name in lowercase."""
    try:
        cleaned = sqlparse.format(sql, strip_comments=True)
        parsed = sqlparse.parse(cleaned)
        if not parsed:
            return None
        
        stmt = parsed[0]
        if stmt.get_type() != "SELECT":
            return None
            
        sql_upper = cleaned.upper()
        # Check if there is a function call/aggregate/subquery in the SELECT projection list
        if "FROM" in sql_upper:
            select_part = sql_upper.split("FROM", 1)[0]
            if "(" in select_part:
                return None

        # If the query contains keywords indicating filtering, joining, or aggregating
        if any(kw in sql_upper for kw in [" WHERE ", " JOIN ", " GROUP BY ", " HAVING ", " UNION ", " INTERSECT ", " EXCEPT ", " DISTINCT "]):
            return None
            
        # Match FROM <table_name> with optional LIMIT/OFFSET or trailing whitespace
        # E.g. SELECT * FROM `consumers` LIMIT 1000 or SELECT id FROM bills
        match = re.search(r'\bFROM\s+`?([a-zA-Z0-9_]+)`?(?:\s+LIMIT|\s+OFFSET|\s*;|\s*$)', sql_upper)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return None


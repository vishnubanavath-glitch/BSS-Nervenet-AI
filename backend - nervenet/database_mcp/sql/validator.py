import logging
import sqlparse
from database_mcp.exceptions import SqlValidationError

logger = logging.getLogger(__name__)

class SQLValidator:
    """Validator to enforce that SQL queries are read-only and free of DDL/DML mutation keywords."""

    FORBIDDEN_KEYWORDS = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", 
        "TRUNCATE", "GRANT", "REVOKE", "REPLACE", "RENAME", "LOAD"
    }

    ALLOWED_KEYWORDS = {"SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"}

    @classmethod
    def validate(cls, sql: str) -> None:
        """Validate the SQL query against read-only safety rules.
        
        Raises:
            SqlValidationError: If the query is empty, malformed, or contains modifying commands.
        """
        if not sql or not sql.strip():
            raise SqlValidationError("SQL query is empty.")

        try:
            statements = sqlparse.parse(sql)
        except Exception as e:
            logger.error(f"Failed to parse SQL: {e}", exc_info=True)
            raise SqlValidationError(f"SQL parsing error: {str(e)}")

        if not statements:
            raise SqlValidationError("No valid SQL statements found.")

        for stmt in statements:
            # Check statement type
            stmt_type = stmt.get_type()
            
            # Skip empty statements (like standalone comments or trailing semicolons)
            has_executable_content = any(
                not token.is_whitespace and token.ttype not in (sqlparse.tokens.Comment, sqlparse.tokens.Comment.Single, sqlparse.tokens.Comment.Multiline)
                for token in stmt.tokens
            )
            if not has_executable_content:
                continue

            if stmt_type in cls.FORBIDDEN_KEYWORDS:
                raise SqlValidationError(f"Forbidden SQL statement type detected: '{stmt_type}'")

            # Check individual tokens recursively to block nested forbidden keywords
            cls._check_tokens(stmt.tokens)

    @classmethod
    def _check_tokens(cls, tokens) -> None:
        """Recursively inspect tokens to ensure no forbidden keywords are present outside of literals/comments."""
        for token in tokens:
            if token.is_group:
                cls._check_tokens(token.tokens)
            else:
                ttype = token.ttype
                
                # Skip comments
                if ttype in (sqlparse.tokens.Comment, sqlparse.tokens.Comment.Single, sqlparse.tokens.Comment.Multiline):
                    continue
                
                # Skip string literals and numbers to avoid false positives on user values (e.g. name = 'DELETE')
                if ttype in sqlparse.tokens.String or ttype in sqlparse.tokens.Literal or ttype in sqlparse.tokens.Number:
                    continue
                
                # Normalize token value
                token_val = str(token.value).upper().strip()
                if token_val in cls.FORBIDDEN_KEYWORDS:
                    raise SqlValidationError(f"Forbidden SQL keyword detected: '{token_val}'")

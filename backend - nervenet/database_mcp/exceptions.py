class DatabaseMcpException(Exception):
    """Base exception for all Database MCP operations, containing structured error details."""
    def __init__(self, message: str, code: str, category: str):
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category

    def to_dict(self) -> dict:
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "category": self.category
            }
        }


class ConfigurationError(DatabaseMcpException):
    """Raised when environment variables or configurations are invalid."""
    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR", category="Configuration")


class ConnectionError(DatabaseMcpException):
    """Raised when the database connection pool setup or connection acquisition fails."""
    def __init__(self, message: str):
        super().__init__(message, code="CONNECTION_ERROR", category="DatabaseConnection")


class MetadataError(DatabaseMcpException):
    """Raised when metadata discovery or caching fails."""
    def __init__(self, message: str):
        super().__init__(message, code="METADATA_ERROR", category="SchemaMetadata")


class SqlValidationError(DatabaseMcpException):
    """Raised when a query violates read-only rules or is syntactically invalid."""
    def __init__(self, message: str):
        super().__init__(message, code="SQL_VALIDATION_ERROR", category="Security")


class SqlExecutionError(DatabaseMcpException):
    """Raised when a query fails during execution in MySQL."""
    def __init__(self, message: str):
        super().__init__(message, code="SQL_EXECUTION_ERROR", category="Execution")


class TimeoutError(DatabaseMcpException):
    """Raised when a database operation times out."""
    def __init__(self, message: str):
        super().__init__(message, code="TIMEOUT_ERROR", category="Execution")


class PermissionDeniedError(DatabaseMcpException):
    """Raised when a resource or action is denied due to permissions."""
    def __init__(self, message: str):
        super().__init__(message, code="PERMISSION_DENIED", category="Security")


class CacheError(DatabaseMcpException):
    """Raised when an operation on the cache fails."""
    def __init__(self, message: str):
        super().__init__(message, code="CACHE_ERROR", category="Cache")


class QueryPlanningError(DatabaseMcpException):
    """Raised when an issue occurs during query cost estimation or optimization."""
    def __init__(self, message: str):
        super().__init__(message, code="QUERY_PLANNING_ERROR", category="Planning")


class SchemaChangedError(DatabaseMcpException):
    """Raised when schema drift is detected."""
    def __init__(self, message: str):
        super().__init__(message, code="SCHEMA_CHANGED_ERROR", category="SchemaMetadata")


class ResourceLimitError(DatabaseMcpException):
    """Raised when query execution exceeds safe limits (like max rows or cost)."""
    def __init__(self, message: str):
        super().__init__(message, code="RESOURCE_LIMIT_ERROR", category="Execution")


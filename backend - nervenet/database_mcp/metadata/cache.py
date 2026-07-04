from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class ColumnMetadata(BaseModel):
    """Metadata representing a database column."""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_target: Optional[str] = None  # Format: "target_table.target_column"

class TableMetadata(BaseModel):
    """Metadata representing a database table."""
    name: str
    columns: Dict[str, ColumnMetadata] = Field(default_factory=dict)
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)  # list of key mappings
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    row_count: int = 0
    data_length: int = 0
    index_length: int = 0
    update_time: Optional[str] = None

class DatabaseMetadata(BaseModel):
    """Overall schema metadata of the database."""
    database_name: str
    tables: Dict[str, TableMetadata] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    metadata_version: int = 1
    schema_version: str = ""
    cache_timestamp: str = ""
    last_refresh: str = ""
    business_domains: Dict[str, List[str]] = Field(default_factory=dict)

class MetadataCache:
    """In-memory cache for storing the loaded schema metadata."""
    def __init__(self):
        self._data: Optional[DatabaseMetadata] = None

    def get(self) -> Optional[DatabaseMetadata]:
        """Retrieve cached metadata."""
        return self._data

    def set(self, data: DatabaseMetadata) -> None:
        """Store metadata in cache."""
        self._data = data

    def clear(self) -> None:
        """Invalidate the cache."""
        self._data = None

    def is_warmed(self) -> bool:
        """Check if metadata cache is populated."""
        return self._data is not None

# Global metadata cache instance
metadata_cache = MetadataCache()

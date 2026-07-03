import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """Database configuration loaded from environment variables and optionally a .env file."""
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="root", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_name: str = Field(default="analytics_demo", alias="DB_NAME")
    
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=10, alias="DB_POOL_MAX_SIZE")
    db_timeout: float = Field(default=30.0, alias="DB_TIMEOUT")
    max_rows_returned: int = Field(default=1000, alias="MAX_ROWS_RETURNED")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

# Singleton configuration instance
settings = Settings()

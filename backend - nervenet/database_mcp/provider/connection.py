import logging
from typing import Optional
import asyncmy
from asyncmy.pool import Pool
from database_mcp.config import settings
from database_mcp.exceptions import ConnectionError

logger = logging.getLogger(__name__)

class ConnectionProvider:
    """Manages the database connection pool using asyncmy."""
    _pool: Optional[Pool] = None

    @classmethod
    async def initialize(cls) -> None:
        """Create the connection pool if it doesn't already exist."""
        if cls._pool is not None:
            return

        try:
            logger.info(
                f"Initializing connection pool to MySQL server at {settings.db_host}:{settings.db_port} "
                f"for database '{settings.db_name}'..."
            )
            cls._pool = await asyncmy.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                db=settings.db_name,
                minsize=settings.db_pool_min_size,
                maxsize=settings.db_pool_max_size,
            )
            logger.info("Connection pool successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}", exc_info=True)
            raise ConnectionError(f"Failed to establish database connection pool: {str(e)}")

    @classmethod
    async def close(cls) -> None:
        """Safely shut down the connection pool."""
        if cls._pool is None:
            return

        try:
            logger.info("Closing database connection pool...")
            cls._pool.close()
            await cls._pool.wait_closed()
            cls._pool = None
            logger.info("Database connection pool closed.")
        except Exception as e:
            logger.error(f"Error during database pool closure: {e}", exc_info=True)

    @classmethod
    def get_pool(cls) -> Pool:
        """Get the underlying connection pool."""
        if cls._pool is None:
            raise ConnectionError("Connection pool has not been initialized. Call initialize() first.")
        return cls._pool

    @classmethod
    def acquire(cls):
        """Context manager to acquire a connection from the pool.
        
        Example usage:
            async with ConnectionProvider.acquire() as conn:
                ...
        """
        pool = cls.get_pool()
        return pool.acquire()

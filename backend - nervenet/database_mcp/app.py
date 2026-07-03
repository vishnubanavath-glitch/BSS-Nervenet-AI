import sys
import os

# Ensure the project root directory is in python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
import anyio
from database_mcp.tools.registry import mcp
from database_mcp.provider.connection import ConnectionProvider
from database_mcp.metadata.loader import MetadataLoader

# Configure logging to go to stderr so it does not corrupt the stdio communication channel
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("database_mcp")

async def main() -> None:
    """Startup workflow for the Database MCP Server."""
    logger.info("Starting Database MCP Server (Version 1)...")
    
    # 1. Initialize MySQL connection pool and test connectivity
    try:
        await ConnectionProvider.initialize()
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        sys.exit(1)

    # 2. Warm the schema metadata cache
    try:
        await MetadataLoader.load_and_cache()
    except Exception as e:
        logger.critical(f"Failed to load schema metadata: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Startup sequence complete. Registering tools and starting FastMCP server...")
    
    # 3. Run the stdio transport server
    try:
        await mcp.run_stdio_async()
    except Exception as e:
        logger.error(f"Error while running server: {e}", exc_info=True)
    finally:
        logger.info("Shutting down Database MCP Server...")
        await ConnectionProvider.close()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    anyio.run(main)

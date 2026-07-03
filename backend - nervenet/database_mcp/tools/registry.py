import logging
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Initialize the FastMCP server instance
mcp = FastMCP("analytics-db-mcp")

# Import tool modules to ensure decorators are executed and registered
from database_mcp.tools import metadata
from database_mcp.tools import sql
from database_mcp.tools import utility
from database_mcp.tools import privacy

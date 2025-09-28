#!/usr/bin/env python3
"""
FastMCP server with HTTP transport for AWS Lambda deployment.
This replaces the need for a proxy by providing direct HTTP endpoints.
"""

from fastmcp import FastMCP
from utils.logger import get_logger

logger = get_logger(__name__)

# Create FastMCP server instance
mcp = FastMCP("daap-mcp-server")

# Import tools so they get registered via decorators
# This follows the pattern from the Medium blog post
import tools


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "daap-mcp-server"}

# For local development
if __name__ == "__main__":
    logger.info("Starting FastMCP server with HTTP transport...")
    mcp.run(transport="http", host="127.0.0.1", port=8000)

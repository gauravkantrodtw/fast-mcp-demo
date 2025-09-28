#!/usr/bin/env python3
"""
FastMCP server with HTTP transport for AWS Lambda deployment.
This replaces the need for a proxy by providing direct HTTP endpoints.
"""

from fastmcp import FastMCP
from utils.logger import get_logger

logger = get_logger(__name__)

# Create FastMCP server instance with proper configuration
mcp = FastMCP("daap-mcp-server")

# Import tools so they get registered via decorators
# This follows the pattern from the Medium blog post
import tools


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "daap-mcp-server"}

# Add resource support (FastMCP standard)
@mcp.resource("system://status")
def get_system_status() -> dict:
    """Returns the current operational status of the service."""
    return {
        "status": "operational",
        "service": "daap-mcp-server",
        "version": "1.0.0",
        "tools_available": 3,
        "uptime": "active"
    }

@mcp.resource("system://info")
def get_server_info() -> dict:
    """Returns detailed information about the MCP server."""
    return {
        "name": "daap-mcp-server",
        "description": "A FastMCP server providing greeting tools and utilities for data analysis and processing.",
        "capabilities": {
            "tools": True,
            "resources": True,
            "logging": True
        },
        "supported_tools": [
            "say_hello",
            "say_goodbye", 
            "get_greeting_info"
        ]
    }

# For local development
if __name__ == "__main__":
    logger.info("Starting FastMCP server with HTTP transport...")
    mcp.run(transport="http", host="127.0.0.1", port=8000)

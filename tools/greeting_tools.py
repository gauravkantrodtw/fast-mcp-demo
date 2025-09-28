#!/usr/bin/env python3
"""
Simple greeting tools for the MCP server.
"""

from utils.logger import get_logger, log_success, log_error
from utils.error_handler import handle_errors, ToolExecutionError

logger = get_logger(__name__)

# Import the MCP server instance to register tools
from server import mcp

@mcp.tool()
@handle_errors("Hello greeting", reraise=True)
def say_hello(name: str = "World") -> str:
    """
    Say hello to someone.
    
    Args:
        name: The name to greet (default: "World")
        
    Returns:
        A friendly greeting message
    """
    logger.info(f"Generating hello greeting for: {name}")
    
    try:
        greeting = f"Hello, {name}! 👋"
        log_success(logger, f"Generated hello greeting for: {name}")
        return greeting
    except Exception as e:
        log_error(logger, f"Hello greeting generation failed", e, name=name)
        raise ToolExecutionError(f"Failed to generate hello greeting for {name}: {e}") from e

@mcp.tool()
@handle_errors("Goodbye greeting", reraise=True)
def say_goodbye(name: str = "Friend") -> str:
    """
    Say goodbye to someone.
    
    Args:
        name: The name to say goodbye to (default: "Friend")
        
    Returns:
        A friendly goodbye message
    """
    logger.info(f"Generating goodbye greeting for: {name}")
    
    try:
        goodbye = f"Goodbye, {name}! See you later! 👋"
        log_success(logger, f"Generated goodbye greeting for: {name}")
        return goodbye
    except Exception as e:
        log_error(logger, f"Goodbye greeting generation failed", e, name=name)
        raise ToolExecutionError(f"Failed to generate goodbye greeting for {name}: {e}") from e

@mcp.tool()
@handle_errors("Greeting tools info", reraise=True)
def get_greeting_info() -> dict:
    """
    Get information about available greeting tools.
    
    Returns:
        A dictionary with greeting tool information
    """
    logger.info("Providing greeting tools information")
    
    try:
        info = {
            "available_tools": ["say_hello", "say_goodbye", "get_greeting_info"],
            "description": "Simple greeting tools for friendly interactions",
            "version": "1.0.0"
        }
        log_success(logger, "Provided greeting tools information")
        return info
    except Exception as e:
        log_error(logger, f"Failed to provide greeting tools info", e)
        raise ToolExecutionError(f"Failed to get greeting tools information: {e}") from e

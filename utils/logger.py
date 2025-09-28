#!/usr/bin/env python3
"""
Centralized logging configuration for the MCP server.
Follows DRY principle by providing a single source of truth for logging setup.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO, format_string: Optional[str] = None) -> None:
    """
    Set up centralized logging configuration.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True  # Override any existing configuration
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_function_call(logger: logging.Logger, func_name: str, **kwargs) -> None:
    """
    Log function call with parameters for debugging.
    
    Args:
        logger: Logger instance
        func_name: Function name being called
        **kwargs: Function parameters to log
    """
    params = ', '.join(f"{k}={v}" for k, v in kwargs.items())
    logger.debug(f"Calling {func_name}({params})")


def log_success(logger: logging.Logger, operation: str, **details) -> None:
    """
    Log successful operation with consistent format.
    
    Args:
        logger: Logger instance
        operation: Description of the operation
        **details: Additional details to log
    """
    detail_str = ', '.join(f"{k}={v}" for k, v in details.items())
    logger.info(f"✅ {operation}" + (f" - {detail_str}" if detail_str else ""))


def log_error(logger: logging.Logger, operation: str, error: Exception, **context) -> None:
    """
    Log error with consistent format and context.
    
    Args:
        logger: Logger instance
        operation: Description of the operation that failed
        error: Exception that occurred
        **context: Additional context information
    """
    context_str = ', '.join(f"{k}={v}" for k, v in context.items())
    logger.error(f"❌ {operation}" + (f" - {context_str}" if context_str else "") + f": {error}")


# Initialize logging for the entire application
setup_logging()

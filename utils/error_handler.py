#!/usr/bin/env python3
"""
Centralized error handling utilities following DRY principle.
Provides consistent error handling patterns across the application.
"""

import logging
from typing import Any, Callable, TypeVar, Optional
from functools import wraps

T = TypeVar('T')
logger = logging.getLogger(__name__)


def handle_errors(
    operation: str,
    default_return: Any = None,
    reraise: bool = False,
    log_level: int = logging.ERROR
) -> Callable:
    """
    Decorator for consistent error handling across functions.
    
    Args:
        operation: Description of the operation for logging
        default_return: Value to return on error (if not reraising)
        reraise: Whether to reraise the exception after logging
        log_level: Logging level for error messages
        
    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log error with context
                context = {
                    'function': func.__name__,
                    'args': str(args)[:100] + '...' if len(str(args)) > 100 else str(args),
                    'kwargs': str(kwargs)[:100] + '...' if len(str(kwargs)) > 100 else str(kwargs)
                }
                
                logger.log(log_level, f"❌ {operation} failed", extra=context, exc_info=True)
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    operation: str,
    *args,
    default_return: Any = None,
    reraise: bool = False,
    **kwargs
) -> T:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        operation: Description of the operation
        *args: Function arguments
        default_return: Value to return on error
        reraise: Whether to reraise the exception
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"❌ {operation} failed: {e}", exc_info=True)
        if reraise:
            raise
        return default_return


class MCPError(Exception):
    """Base exception for MCP server errors."""
    pass


class ToolExecutionError(MCPError):
    """Exception raised when tool execution fails."""
    pass


class ConfigurationError(MCPError):
    """Exception raised when configuration is invalid."""
    pass

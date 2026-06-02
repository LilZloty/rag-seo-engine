"""
Structured logging configuration for RAG SEO Engine
Uses loguru for beautiful, structured logs with JSON support
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


# Default log directory
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = "app.log",
    json_format: bool = False,
    serialize: bool = False
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Name of the log file (None to disable file logging)
        json_format: Use JSON format for logs
        serialize: Serialize log output to JSON (useful for log aggregation)
    """
    # Remove default handler
    logger.remove()
    
    # Console output with colors
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}:{function}:{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=log_format,
        level=log_level,
        colorize=True
    )
    
    # File output
    if log_file:
        log_path = LOG_DIR / log_file
        if json_format:
            file_format = (
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level} | "
                "{name}:{function}:{line} | "
                "{message} | {extra}"
            )
        else:
            file_format = (
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "<level>{level: <8}</level> | "
                "{name}:{function}:{line} | "
                "<level>{message}</level>"
            )
        
        logger.add(
            log_path,
            format=file_format,
            level=log_level,
            rotation="10 MB",
            retention="10 days",  # Duration format for loguru
            compression="gz",
            serialize=serialize,
            encoding="utf-8"
        )
        
        # Also create an error-only log file
        error_log_path = LOG_DIR / "errors.log"
        logger.add(
            error_log_path,
            format=file_format,
            level="ERROR",
            rotation="10 MB",
            retention="10 days",  # Duration format for loguru
            compression="gz",
            encoding="utf-8"
        )
    
    # Add context enrichment
    logger.configure(
        extra={
            "request_id": "",
            "user_id": "",
            "product_id": "",
            "session_id": "",
        }
    )


def get_logger(name: str):
    """
    Get a logger with the specified name.
    
    Args:
        name: Name of the logger (usually __name__)
    
    Returns:
        Logger instance
    """
    return logger.bind(module=name)


# Auto-configure based on environment
import os
if not os.environ.get("APP_TESTING"):
    try:
        env = os.environ.get("ENVIRONMENT", "development")
        is_prod = env == "production"
        setup_logging(
            log_level=os.environ.get("LOG_LEVEL", "WARNING" if is_prod else "INFO"),
            json_format=is_prod,
            serialize=is_prod,
        )
    except Exception:
        pass

__all__ = ["logger", "setup_logging", "get_logger"]

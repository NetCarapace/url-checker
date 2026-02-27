"""
Structured logging utilities for the URLChecker application.

This module provides a structured JSON logger and route logging functionality
for consistent logging throughout the Flask application.
"""

import inspect
import sys
import traceback

import commentjson
from flask import current_app, request, session


class StructuredLogger:
    """Wrapper to provide structured JSON logging with familiar log.level style."""

    def _log(
        self, level: str, message: str, extra: dict = None, exc_info: bool = False
    ):
        """
        Internal method to create and emit structured log entries.

        Args:
            level: Log level (info, error, warning, debug)
            message: Log message
            extra: Additional context data
            exc_info: If True, adds exception traceback to log entry
        """
        try:
            # Try to get frame info, but handle cases where it might fail
            frame = inspect.currentframe()
            if frame and frame.f_back and frame.f_back.f_back:
                action = frame.f_back.f_back.f_code.co_name
            else:
                action = "unknown"
        except Exception:
            action = "unknown"

        log_entry = {
            "action": action,
            "message": message,
        }

        # Safely add request/session info if available
        try:
            log_entry.update(
                {
                    "username": session.get("username"),
                    "tenants": session.get("tenants"),
                    "path": request.path,
                    "method": request.method,
                }
            )
        except RuntimeError:
            # Outside of request context
            pass

        # Add exception info if requested
        if exc_info:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_type is not None:
                log_entry["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "traceback": traceback.format_tb(exc_traceback),
                }

        if extra:
            log_entry.update(extra)

        log_json = commentjson.dumps(log_entry)

        # Safely get logger - use Python's built-in logging if Flask app not available
        try:
            logger = current_app.logger
        except RuntimeError:
            # Fall back to Python's built-in logger
            import logging

            logger = logging.getLogger(__name__)

        getattr(logger, level)(log_json)

    def info(self, message: str, extra: dict = None, exc_info: bool = False):
        """
        Log an informational message with structured data.

        Args:
            message (str): The informational message
            extra (dict, optional): Additional context data for the log entry
        """
        self._log("info", message, extra, exc_info)

    def error(self, message: str, extra: dict = None, exc_info: bool = False):
        """
        Log an error message with structured data.

        Args:
            message (str): The error message
            extra (dict, optional): Additional context data for the log entry
        """
        self._log("error", message, extra, exc_info)

    def warning(self, message: str, extra: dict = None, exc_info: bool = False):
        """
        Log a warning message with structured data.

        Args:
            message (str): The warning message
            extra (dict, optional): Additional context data for the log entry
        """
        self._log("warning", message, extra, exc_info)

    def debug(self, message: str, extra: dict = None, exc_info: bool = False):
        """
        Log a debug message with structured data.

        Args:
            message (str): The debug message
            extra (dict, optional): Additional context data for the log entry
        """
        self._log("debug", message, extra, exc_info)


# Shared instance
log = StructuredLogger()


def init_route_logging(app):
    """
    Initialize global route logging for all routes.
    Only active when Flask app is in debug mode.

    Args:
        app: The Flask application instance
    """

    @app.before_request
    def log_route_entry():
        """Log before each request when in debug mode."""
        if app.debug:
            log.info(
                "Route entered",
                extra={
                    "endpoint": request.endpoint,
                    "path": request.path,
                    "method": request.method,
                    "url": request.url,
                    "username": session.get("username"),
                },
            )

    @app.after_request
    def log_route_exit(response):
        """Log after each request when in debug mode."""
        if app.debug:
            log.info(
                "Route completed",
                extra={
                    "endpoint": request.endpoint,
                    "path": request.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "username": session.get("username"),
                },
            )
        return response

    # Note: teardown_request runs even if there's an exception
    @app.teardown_request
    def log_route_errors(exc=None):
        """Log route errors when in debug mode."""
        if app.debug and exc is not None:
            log.error(
                f"Route error: {exc}",
                extra={
                    "endpoint": request.endpoint,
                    "path": request.path,
                    "method": request.method,
                    "username": session.get("username"),
                },
            )

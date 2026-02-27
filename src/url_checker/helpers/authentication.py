"""
Authorization utilities for the URLChecker application.

This module provides user authentication and
authentication decorators for securing Flask routes.
"""

from functools import wraps

from flask import current_app, jsonify, request


def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Despite we deal with Autorization header, we are still authenticating the requester ...
        # Currently, the token simply gives autorization to all api by design.
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Authorization header is missing"}), 401

        # Enforce Bearer scheme
        if not auth_header.startswith("Bearer "):
            return (
                jsonify({"error": "Authorization header must use Bearer scheme"}),
                401,
            )

        # Remove 'Bearer ' prefix
        token = auth_header.split(" ", 1)[1]

        # Validate against database or environment variable
        if not validate_token(token):  # Your validation function
            return jsonify({"error": "Invalid token or missing"}), 401

        return f(*args, **kwargs)

    return decorated_function


def validate_token(token):
    # Check against database, environment variable, or other storage
    # Return True if valid, False otherwise
    return token == current_app.config["API_TOKEN"]

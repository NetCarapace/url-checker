from datetime import timedelta
from pathlib import Path

from flask import (
    current_app,
    jsonify,
)

from url_checker.admin import admin
from url_checker.helpers.authentication import require_api_token


def serialize_and_hide_sensitive_config(config):
    """Serialize to JSON-compatible types and Hide sensitive fields ending with PASSWORD, SECRET, or KEY"""
    cleant_config = {}
    patterns = ["PASSWORD", "SECRET", "KEY", "TOKEN"]
    if not current_app.config["DEBUG"]:
        # URL and URI may contain password, do not show in Prod !
        patterns.append("URL")
        patterns.append("URI")
        patterns.append("CELERY_BACKEND_RESULT")
        patterns.append("SQLALCHEMY_DATABASE_URI")
        patterns.append("PASS")
    for key, value in config.items():
        # Redact sensitive keys
        if any(pattern in key for pattern in patterns):
            cleant_config[key] = "***"
        else:
            cleant_config[key] = serialize_value(value)

    return cleant_config


def serialize_value(value):
    """Convert non-JSON-serializable types to serializable ones"""
    if isinstance(value, Path):
        return str(value)
    elif isinstance(value, timedelta):
        return value.total_seconds()
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value


@admin.route("/", methods=["GET"])
@require_api_token
def hello():
    return "Hello, Admin!"


@admin.route("/settings", methods=["GET"])
def get_settings():
    app_config = dict(current_app.config)
    cleant_config = serialize_and_hide_sensitive_config(app_config)
    response = {"app_config": cleant_config}

    return jsonify(response), 200

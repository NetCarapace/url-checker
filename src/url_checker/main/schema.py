"""
Marshmallow schemas for request validation.
Used for API endpoint input validation.
"""

from urllib.parse import urlparse

from marshmallow import Schema, ValidationError, fields, post_load, validates

from url_checker.main.enums import URLScheme, ValidationResult
from url_checker.settings.settings import settings


class URLValidationSchema(Schema):
    """
    Schema for validating URL input in API requests.

    This validates the basic structure and format, but doesn't
    perform deep validation (that's done by the ValidationJob).
    """

    url = fields.Str(
        required=True,
        error_messages={
            "required": "URL is required",
            "null": "URL cannot be null",
            "invalid": "URL must be a string",
        },
    )

    @validates("url")
    # Kepp **kwargs for Marshmallow 4.x
    def validate_url_format(self, value, **kwargs):
        # Check length
        if len(value) > settings.url["max_length"]:
            raise ValidationError(
                f"URL exceeds maximum length of {settings.url['max_length']} characters"
            )

        # Check for whitespace
        if value != value.strip():
            raise ValidationError("URL contains leading or trailing whitespace")

        # Check for obvious invalid characters
        if any(char in value for char in [" ", "\n", "\r", "\t"]):
            raise ValidationError("URL contains invalid whitespace characters")

        # Parse URL
        try:
            parsed = urlparse(value)
        except Exception as e:
            raise ValidationError(
                f"{ValidationResult.INVALID_FORMAT.label}: {str(e)}"
            ) from e

        if not parsed.scheme:
            raise ValidationError(ValidationResult.MISSING_SCHEME.label)

        if not parsed.netloc:
            raise ValidationError(ValidationResult.MISSING_DOMAIN.label)

        if parsed.scheme.lower() not in URLScheme.valid_schemes():
            raise ValidationError(
                f"{ValidationResult.INVALID_SCHEME.label}: "
                f"'{parsed.scheme}' is not supported. "
                f"Must be one of {', '.join(URLScheme.valid_schemes())}"
            )

    @post_load
    def normalize_url(self, data, many, **kwargs):
        """Normalize URL after validation"""
        url = data["url"].strip()

        # Optionally normalize scheme to lowercase
        parsed = urlparse(url)
        if parsed.scheme != parsed.scheme.lower():
            url = url.replace(parsed.scheme, parsed.scheme.lower(), 1)

        data["url"] = url
        return data


class AnalysisQuerySchema(Schema):
    """Schema for querying analysis results"""

    status = fields.Str(
        required=False, validate=lambda s: s in ["pending", "completed", "failed"]
    )
    limit = fields.Int(
        required=False, validate=lambda n: 1 <= n <= 100, load_default=20
    )
    offset = fields.Int(required=False, validate=lambda n: n >= 0, load_default=0)

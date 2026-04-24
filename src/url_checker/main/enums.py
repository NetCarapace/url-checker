from enum import Enum
from typing import Optional

from url_checker.settings.custom_types import JobTypeConfig

# ========================================
# A custom ChoiceEnum on-top of Enum
# ========================================


class ChoiceEnum(str, Enum):
    """
    Base enum class with Django-style choices support
    Subclasses define tuples: CODE = (value, label, description)
    """

    def __new__(cls, value, label, description=None):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._label_ = label
        obj._description_ = description
        return obj

    @property
    def label(self):
        """Human-readable label"""
        return self._label_

    @property
    def description(self):
        """Detailed description"""
        return self._description_

    @classmethod
    def choices(cls):
        """Get list of (value, label) tuples for forms/dropdowns"""
        return [(item.value, item.label) for item in cls]

    @classmethod
    def choices_with_description(cls):
        """Get list of (value, label, description) tuples"""
        return [(item.value, item.label, item.description) for item in cls]

    @classmethod
    def get_label(cls, value):
        """Get label for a given value"""
        for item in cls:
            if item.value == value:
                return item.label
        return value

    @classmethod
    def get_description(cls, value):
        """Get description for a given value"""
        for item in cls:
            if item.value == value:
                return item.description
        return None

    @classmethod
    def values(cls):
        """Get list of all values"""
        return [item.value for item in cls]


# ========================================
# Status Enums
# ========================================


class ValidityStatus(ChoiceEnum):
    """
    URL validity status - from Job1 (Validation)
    Indicates whether URL format and scheme are valid
    """

    INVALID = ("INVALID", "Invalid", "URL format or scheme is invalid")

    VALID_NON_HTTP = (
        "VALID_NON_HTTP",
        "Valid (Non-HTTP)",
        "URL is valid but uses non-HTTP scheme (FTP, SSH, etc.)",
    )

    VALID_HTTP = (
        "VALID_HTTP",
        "Valid (HTTP/HTTPS)",
        "URL is valid and uses HTTP or HTTPS scheme",
    )

    # TODO Check where this one should be used ! -> most probably in the validator !
    UNKNOWN = ("UNKNOWN", "Unknown", "Validation job was inconclusive or not completed")


class ReachabilityStatus(ChoiceEnum):
    """
    URL reachability status - from Job2 (Ping)
    Indicates whether URL domain is reachable
    """

    REACHABLE = ("REACHABLE", "Reachable", "Domain responds from URL Checker host")

    UNREACHABLE = (
        "UNREACHABLE",
        "Unreachable",
        "Domain does not respond to ping requests",
    )

    NOT_CHECKED = (
        "NOT_CHECKED",
        "Not Checked",
        "Reachability check was skipped (invalid URL or non-HTTP scheme)",
    )


class SecurityStatus(ChoiceEnum):
    """
    URL security/security status - from Job3 (Security Check)
    Indicates whether URL poses security risks
    """

    SAFE = ("SAFE", "Safe", "URL passed all security checks")

    UNSAFE = ("UNSAFE", "Unsafe", "URL failed one or more security checks")

    UNKNOWN = ("UNKNOWN", "Unknown", "Security check not run or inconclusive")

    @classmethod
    def _missing_(cls, value):
        """
        Handle None values - returns UNKNOWN
        Allows storing NULL in database which maps to UNKNOWN
        """
        if value is None:
            return cls.UNKNOWN
        return None


class JobStatus(ChoiceEnum):
    """
    Job execution status
    Tracks the lifecycle of a Celery task
    """

    PENDING = ("PENDING", "Pending", "Job is queued and waiting to start")

    STARTED = (
        "STARTED",
        "Started",
        "Job has been picked up by a worker and is starting",
    )

    SUCCESS = ("SUCCESS", "Success", "Job completed successfully")

    FAILED = ("FAILED", "Failed", "Job completed with errors")

    SKIPPED = ("SKIPPED", "Skipped", "Job was skipped due to previous job results")

    RETRY = ("RETRY", "Retrying", "Job failed and is being retried")


class ValidationResult(ChoiceEnum):
    """
    URL validation error results
    Specific reasons why URL validation failed
    """

    VALID = ("VALID", "Valid", "URL passed all validation checks")

    INVALID_FORMAT = ("INVALID_FORMAT", "Invalid Format", "URL format is malformed")

    INVALID_SCHEME = ("INVALID_SCHEME", "Invalid Scheme", "URL scheme is not supported")

    MISSING_DOMAIN = (
        "MISSING_DOMAIN",
        "Missing Domain",
        "URL does not contain a domain name",
    )

    MISSING_SCHEME = (
        "MISSING_SCHEME",
        "Missing Scheme",
        "URL does not specify a scheme (http://, https://, etc.)",
    )


# ========================================
# Configuration Enums
# ========================================


class URLScheme(ChoiceEnum):
    """
    Supported URL schemes
    Defines which protocols can be analyzed
    """

    HTTP = ("http", "HTTP", "Hypertext Transfer Protocol (unencrypted)")

    HTTPS = ("https", "HTTPS", "Hypertext Transfer Protocol Secure (encrypted)")

    FTP = ("ftp", "FTP", "File Transfer Protocol (unencrypted)")

    FTPS = ("ftps", "FTPS", "File Transfer Protocol Secure (encrypted)")

    SSH = ("ssh", "SSH", "Secure Shell Protocol")

    SAMBA = ("samba", "SAMBA", "SAMBA")

    SMB = ("smb", "samba", "samba")

    LOCALHOST = ("localhost", "localhost", "localhost")

    MAILTO = ("mailto", "mailto", "mailto")

    # Even this works with edu.lu !
    # This shows that we must restrain the type of url to shorten
    # TEST = ("test", "test", "test")

    @classmethod
    def is_http_scheme(cls, scheme: str) -> bool:
        """Check if scheme is HTTP/HTTPS"""
        return scheme.lower() in [cls.HTTP.value, cls.HTTPS.value]

    @classmethod
    def valid_schemes(cls) -> list:
        """Get list of valid scheme strings"""
        return [s.value for s in cls]

    @classmethod
    def http_schemes(cls) -> list:
        """Get list of HTTP-based schemes"""
        return [cls.HTTP.value, cls.HTTPS.value]

    @classmethod
    def secure_schemes(cls) -> list:
        """Get list of secure/encrypted schemes"""
        return [cls.HTTPS.value, cls.FTPS.value, cls.SSH.value]


class JobTypeCode(ChoiceEnum):
    """
    Job type definitions.
    Loaded from Flask Config at runtime.

    Example: call JobTypeCode("VALIDATION_CHECK").label -> no need for explicit getter method
    as we are supposed to always call Enums that exist.
    """

    VALIDATION_CHECK = (
        "VALIDATION_CHECK",
        "URL Validation Check",
        "Validates URL format, scheme, and basic structure",
    )

    REACHABILITY_CHECK = (
        "REACHABILITY_CHECK",
        "Reachability Check",
        "Checks if the URL domain is reachable via ping/HTTP HEAD",
    )

    SECURITY_CHECK = (
        "SECURITY_CHECK",
        "Security Check",
        "Performs malware, phishing, and security threat detection",
    )

    # Future job types (commented out until implemented)
    # WHOIS = (
    #     "whois_check",
    #     "WHOIS Lookup",
    #     "Query WHOIS information for domain registration details"
    # )

    # DNS_LOOKUP = (
    #     "dns_lookup",
    #     "DNS Lookup",
    #     "Resolve DNS records for the domain"
    # )
    def get_config(self, app_config: Optional[dict] = None) -> "JobTypeConfig":
        """
        Get runtime configuration for this job type, with flexibility given to the caller
        to decide if a Flask context exists

        Args:
            app_config: Optional Flask app.config dict.
                       If None, uses global settings.

        Returns:
            JobTypeConfig for this job type

        Usage:
            # Default - works everywhere
            config = JobTypeCode.VALIDATION_CHECK.get_config()

            # Override with Flask app config
            config = JobTypeCode.VALIDATION_CHECK.get_config(current_app.config)
        """
        if app_config is not None:
            # Use Flask app config if provided (from current_app generally)
            return app_config["JOB_TYPES_CONFIG"].get(self)
        else:
            # Use global settings (works everywhere)
            from url_checker.settings.settings import settings

            return settings.job_types_config.get(self)

    @property
    def tools_path(self) -> str:
        return self.get_config().tools_path

    @property
    def tools_command(self) -> str:
        return self.get_config().tools_command

    @property
    def tools_env_file(self) -> str:
        return self.get_config().tools_env_file

    @property
    def timeout_seconds(self) -> int:
        return self.get_config().timeout_seconds

    @property
    def max_retries(self) -> int:
        return self.get_config().max_retries

    @property
    def retry_delay_seconds(self) -> int:
        return self.get_config().retry_delay_seconds


# ========================================
# Usage Examples
# ========================================

if __name__ == "__main__":
    # Get choices for dropdown (Django-style)
    print("Job Status Choices:")
    print(JobStatus.choices())
    # [('PENDING', 'Pending'), ('STARTED', 'Started'), ...]

    # Get choices with descriptions
    print("\nJob Type Choices with Descriptions:")
    print(JobTypeCode.choices_with_description())
    # [('url_validation', 'URL Validation', 'Validate URL format...'), ...]

    # Access enum properties
    status = ValidityStatus.VALID_HTTP
    print(f"\nValue: {status.value}")  # "VALID_HTTP"
    print(f"Label: {status.label}")  # "Valid (HTTP/HTTPS)"
    print(f"Description: {status.description}")  # "URL is valid and uses..."

    # Get label from value
    label = JobStatus.get_label("PROCESSING")
    print(f"\nLabel for PROCESSING: {label}")  # "Processing"

    # Check if scheme is HTTP
    is_http = URLScheme.is_http_scheme("https")
    print(f"\nIs HTTPS an HTTP scheme? {is_http}")  # True

    # Get all valid schemes
    schemes = URLScheme.valid_schemes()
    print(f"\nValid schemes: {schemes}")  # ['http', 'https', 'ftp', 'ftps', 'ssh']

    # Check if status is terminal
    is_done = JobStatus.is_terminal("SUCCESS")
    print(f"\nIs SUCCESS terminal? {is_done}")  # True

    job_type = JobTypeCode.VALIDATION_CHECK
    print(job_type.tools_command)  # From config
    print(job_type.tools_env_file)  # From config
    print(job_type.timeout_seconds)  # 10

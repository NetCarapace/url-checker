# validators.py
"""
URL validation module.
Contains validators for deep URL inspection (Job1: URL Validation).
"""

import ipaddress
import re
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import ParseResult, urlparse

from url_checker.main.enums import URLScheme, ValidationResult, ValidityStatus


@dataclass
class URLValidationResult:
    """Result of URL validation"""

    is_valid: bool
    validity_status: str
    validation_result: str
    details: Dict[str, any]
    error_message: Optional[str] = None


class URLValidator:
    """
    Deep URL validator for Job1 (URL Validation).

    Performs comprehensive validation including:
    - Format validation
    - Scheme validation
    - Domain validation
    - IP address detection
    - Security checks
    """

    # Domain name regex (RFC 1035)
    DOMAIN_REGEX = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
        r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
    )

    # Maximum domain length
    MAX_DOMAIN_LENGTH = 253
    MAX_LABEL_LENGTH = 63

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        r"@",  # @ in URL (phishing)
        r"\.{2,}",  # Multiple consecutive dots
        r"-{3,}",  # Multiple consecutive hyphens
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",  # IP address (flagged)
    ]

    def __init__(self, url: str, settings=None):
        """
        Initialize validator with URL.

        Args:
            url: URL string to validate
            settings: Optional settings object (for custom rules)
        """
        self.url = url.strip()
        self.settings = settings
        self.parsed: Optional[ParseResult] = None

    # Private methods
    def _parse_url(self) -> Dict:
        """Parse URL and check basic structure"""
        try:
            parsed = urlparse(self.url)

            if not parsed.scheme:
                return {
                    "is_valid": False,
                    "error": ValidationResult.MISSING_SCHEME.label,
                }

            if not parsed.netloc:
                return {
                    "is_valid": False,
                    "error": ValidationResult.MISSING_DOMAIN.label,
                }

            return {
                "is_valid": True,
                "parsed": parsed,
            }

        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Failed to parse URL: {str(e)}",
            }

    def _validate_scheme(self) -> Dict:
        """Validate URL scheme"""
        scheme = self.parsed.scheme.lower()

        if scheme not in URLScheme.valid_schemes():
            return {
                "is_valid": False,
                "error": f"Unsupported scheme: {scheme}",
                "allowed_schemes": URLScheme.valid_schemes(),
            }

        return {
            "is_valid": True,
            "scheme": scheme,
            "is_http": URLScheme.is_http_scheme(scheme),
            "is_secure": scheme in URLScheme.secure_schemes(),
        }

    def _validate_domain(self) -> Dict:
        """Validate domain name or IP address"""
        netloc = self.parsed.netloc

        # Remove port if present
        domain = netloc.split(":")[0]

        if not domain:
            return {
                "is_valid": False,
                "error": "Domain is empty",
            }

        # Check if it's an IP address
        ip_result = self._check_ip_address(domain)
        if ip_result["is_ip"]:
            return {
                "is_valid": True,
                "is_ip_address": True,
                "ip_version": ip_result["version"],
                "domain": domain,
            }

        # Validate as domain name
        domain_result = self._validate_domain_name(domain)

        return domain_result

    def _check_ip_address(self, domain: str) -> Dict:
        """Check if domain is an IP address"""
        try:
            ip = ipaddress.ip_address(domain)
            return {
                "is_ip": True,
                "version": f"IPv{ip.version}",
                "is_private": ip.is_private,
                "is_loopback": ip.is_loopback,
            }
        except ValueError:
            return {"is_ip": False}

    def _validate_domain_name(self, domain: str) -> Dict:
        """Validate domain name according to RFC 1035"""

        # Remove brackets for IPv6
        if domain.startswith("[") and domain.endswith("]"):
            domain = domain[1:-1]

        # Check length
        if len(domain) > self.MAX_DOMAIN_LENGTH:
            return {
                "is_valid": False,
                "error": f"Domain exceeds maximum length ({self.MAX_DOMAIN_LENGTH})",
            }

        # Check each label
        labels = domain.split(".")

        for label in labels:
            if not label:
                return {
                    "is_valid": False,
                    "error": "Domain contains empty label",
                }

            if len(label) > self.MAX_LABEL_LENGTH:
                return {
                    "is_valid": False,
                    "error": f"Domain label '{label}' exceeds maximum length ({self.MAX_LABEL_LENGTH})",
                }

            # Check label format
            if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$", label):
                return {
                    "is_valid": False,
                    "error": f"Invalid domain label: '{label}'",
                }

        # Must have at least TLD
        if len(labels) < 2:
            return {
                "is_valid": False,
                "error": "Domain must have at least a subdomain and TLD",
            }

        return {
            "is_valid": True,
            "is_ip_address": False,
            "domain": domain,
            "labels": labels,
            "tld": labels[-1],
        }

    def _check_security_issues(self) -> Dict:
        """Check for suspicious patterns"""
        flags = []

        # Check for suspicious patterns
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, self.url):
                flags.append(f"Suspicious pattern: {pattern}")

        # Check for @ symbol (phishing)
        if "@" in self.parsed.netloc:
            flags.append("Contains @ symbol (potential phishing)")

        # Check for IP address (often suspicious)
        if self._check_ip_address(self.parsed.netloc.split(":")[0])["is_ip"]:
            flags.append("Uses IP address instead of domain")

        # Check for excessive length
        if len(self.url) > 2000:
            flags.append("URL is excessively long")

        # Check for unusual port
        if self.parsed.port:
            if self.parsed.scheme in ["http", "https"]:
                if self.parsed.port not in [80, 443, 8080, 8443]:
                    flags.append(f"Unusual port: {self.parsed.port}")

        return {
            "flags": flags,
            "has_issues": len(flags) > 0,
        }

    # Public methods
    def validate(self) -> URLValidationResult:
        """
        Perform complete validation.

        Returns:
            URLValidationResult with validation details
        """
        # Step 1: Parse URL
        parse_result = self._parse_url()
        if not parse_result["is_valid"]:
            return URLValidationResult(
                is_valid=False,
                validity_status=ValidityStatus.INVALID.value,
                validation_result=ValidationResult.INVALID_FORMAT.value,
                details=parse_result,
                error_message=parse_result.get("error"),
            )

        self.parsed = parse_result["parsed"]

        # Step 2: Validate scheme
        scheme_result = self._validate_scheme()
        if not scheme_result["is_valid"]:
            return URLValidationResult(
                is_valid=False,
                validity_status=ValidityStatus.INVALID.value,
                validation_result=ValidationResult.INVALID_SCHEME.value,
                details=scheme_result,
                error_message=scheme_result.get("error"),
            )

        # Step 3: Validate domain/netloc
        domain_result = self._validate_domain()
        if not domain_result["is_valid"]:
            return URLValidationResult(
                is_valid=False,
                validity_status=ValidityStatus.INVALID.value,
                validation_result=ValidationResult.MISSING_DOMAIN.value,
                details=domain_result,
                error_message=domain_result.get("error"),
            )

        # Step 4: Security checks
        security_result = self._check_security_issues()

        # Determine validity status
        if URLScheme.is_http_scheme(self.parsed.scheme):
            validity_status = ValidityStatus.VALID_HTTP.value
        else:
            validity_status = ValidityStatus.VALID_NON_HTTP.value

        # Combine all details
        details = {
            "scheme": self.parsed.scheme,
            "domain": self.parsed.netloc,
            "path": self.parsed.path,
            "is_http": URLScheme.is_http_scheme(self.parsed.scheme),
            "is_ip_address": domain_result.get("is_ip_address", False),
            "has_port": bool(self.parsed.port),
            "port": self.parsed.port,
            "security_flags": security_result.get("flags", []),
        }

        return URLValidationResult(
            is_valid=True,
            validity_status=validity_status,
            validation_result=ValidationResult.VALID.value,
            details=details,
            error_message=None,
        )


def validate_url(url: str, settings=None) -> URLValidationResult:
    """
    Convenience function to validate a URL.

    Args:
        url: URL string to validate
        settings: Optional settings object

    Returns:
        URLValidationResult

    Example:
        >>> result = validate_url("https://example.com")
        >>> if result.is_valid:
        >>>     print(f"Valid URL: {result.validity_status}")
    """
    validator = URLValidator(url, settings)
    return validator.validate()

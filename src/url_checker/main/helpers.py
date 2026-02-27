from url_checker.main.enums import ReachabilityStatus, SecurityStatus, ValidityStatus
from url_checker.main.models import URL


def get_url_overall_status(url: URL) -> dict:
    """
    Get overall status summary for a URL

    Returns:
        {
            'validity': 'VALID_HTTP',
            'reachability': 'REACHABLE',
            'security': 'SAFE',
            'overall': 'SAFE'  # or 'UNSAFE', 'INVALID', 'UNREACHABLE', etc.
        }
    """
    # TODO THIS MAKE NOT LOT OF SENSE
    # Determine overall status based on hierarchy
    if url.validity_status == ValidityStatus.INVALID.value:
        overall = "INVALID"
    elif url.reachability_status == ReachabilityStatus.UNREACHABLE.value:
        overall = "UNREACHABLE"
    elif url.security_status == SecurityStatus.UNSAFE.value:
        overall = "UNSAFE"
    elif url.security_status == SecurityStatus.SAFE.value:
        overall = "SAFE"
    elif url.security_status is None:
        overall = "PENDING_SECURITY_CHECK"
    else:
        overall = "UNKNOWN"

    return {
        "validity": url.validity_status,
        "reachability": url.reachability_status,
        "security": url.security_status,
        "overall": overall,
    }

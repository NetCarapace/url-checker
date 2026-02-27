"""Helper Functions for our simple Tasks manager"""

import json
import subprocess
from urllib.parse import urlparse

from url_checker.helpers.logging import log
from url_checker.main.enums import (
    JobStatus,
    JobTypeCode,
    ReachabilityStatus,
    SecurityStatus,
)
from url_checker.main.models import Result


def build_command(job_type_code: str, config, url_normalized: str):
    """
    Build command based on job type.

    Returns:
        tuple: (command_list, target_string)
    """
    parsed = urlparse(url_normalized)

    if job_type_code == JobTypeCode.REACHABILITY_CHECK.value:
        # Job2: Ping domain needs specific treatment of url
        domain = parsed.netloc.split(":")[0]  # Remove port if present
        target = domain
    elif job_type_code == JobTypeCode.SECURITY_CHECK.value:
        # Job3: Security check on full URL
        target = url_normalized
    else:
        raise ValueError(f"Unknown job_type_code: {job_type_code}")

    command_str = str(config.tools_command)
    command_parts = command_str.split()

    if config.tools_path:
        command_parts[0] = str(config.tools_path / command_parts[0])

        #    TODO Small hack for v0.2 in order to simulate a security_check before actually plugging in it
        if command_parts[0].endswith("sleep"):
            # Don't append URL to sleep command
            command = command_parts
        else:
            # When ready, remove if and use only this:
            command = command_parts + [target]

    return command, target


def execute_tool(job_id: int, command: list, cwd: str, timeout: int) -> dict:
    """
    Execute external tool and capture output.

    Returns:
        dict: {
            'success': bool,
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'error': str or None
        }
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )

        log.info(f"Job {job_id}: Tool exit code: {result.returncode}")

        return {
            "success": True,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": None,
        }

    except subprocess.TimeoutExpired:
        log.warning(f"Job {job_id}: Tool timeout after {timeout}s")
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Timeout after {timeout}s",
        }

    except Exception as e:
        log.error(f"Job {job_id}: Execution error: {e}", exc_info=True)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "error": str(e),
        }


def handle_reachability_success(job_id: int, result: dict, execution_result: dict):
    """
    Handle Job2 (Reachability) success - parse ping output

    Must be run from within the FlaskApp context
    """

    is_reachable = execution_result["exit_code"] == 0 and not execution_result.get(
        "error"
    )

    # Determine status
    job_error_logs = ""
    if is_reachable:
        reachability_status = ReachabilityStatus.REACHABLE.value
        job_status = JobStatus.SUCCESS.value
    else:
        reachability_status = ReachabilityStatus.UNREACHABLE.value
        job_status = (
            JobStatus.SUCCESS.value
        )  # Job succeeded (ping ran), URL is just unreachable
        job_error_logs = execution_result.get("error") or execution_result.get("stderr")

    log.info(f"Job {job_id}: Reachability={reachability_status}")

    # Build output
    output_data = {
        "is_reachable": is_reachable,
        "target": result["target"],
        "exit_code": execution_result["exit_code"],
        "stdout": execution_result["stdout"][:1000],  # Limit size
        "stderr": execution_result["stderr"][:500],
    }

    # Create Result recordexecution_result
    result_record = Result(
        job_id=job_id,
        output=json.dumps(output_data, indent=2),
        validity_status="",
        reachability_status=reachability_status,
        security_status="",
    )
    return job_status, job_error_logs, result_record


def handle_security_success(job_id: int, result: dict, execution_result: dict):
    """
    Handle Job3 (Security) success - parse JSON security output

    Must be run from within the FlaskApp context
    """

    stdout = execution_result["stdout"]
    stderr = execution_result["stderr"]

    # Try to parse JSON output from security tool
    try:
        security_result_json = json.loads(stdout)
        log.info(f"Job {job_id}: Parsed JSON security result successfully")
    except json.JSONDecodeError as e:
        log.error(f"Job {job_id}: Failed to parse JSON output: {e}")
        log.error(f"Job {job_id}: Raw output: {stdout[:500]}")

        # If JSON parse fails, treat as unknown
        security_result_json = {
            "status": "unknown",
            "error": f"Failed to parse tool output: {str(e)}",
            "raw_output": stdout[:1000],
            "stderr": stderr[:1000],
        }

    # Parse status
    tool_status = security_result_json.get("status", "unknown").lower()

    job_error_logs = ""
    if tool_status == "safe":
        security_status = SecurityStatus.SAFE.value
        job_status = JobStatus.SUCCESS.value
    elif tool_status == "unsafe":
        security_status = SecurityStatus.UNSAFE.value
        job_status = JobStatus.SUCCESS.value  # Job succeeded, URL is unsafe
        threats = security_result_json.get("threats", [])
        job_error_logs = (
            f"Security threats detected: {', '.join(threats)}"
            if threats
            else "URL flagged as unsafe"
        )
    else:  # unknown or error
        security_status = SecurityStatus.UNKNOWN.value
        job_status = JobStatus.FAILED.value
        job_error_logs = security_result_json.get(
            "error", "Security check inconclusive"
        )

    log.info(f"Job {job_id}: Security status={security_status}")

    # Create Result record
    result_record = Result(
        job_id=job_id,
        output=json.dumps(security_result_json, indent=2)[
            :5000
        ],  # Store JSON, limit size
        validity_status="",
        reachability_status="",
        security_status=security_status,
    )
    return job_status, job_error_logs, result_record

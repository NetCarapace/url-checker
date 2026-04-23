"""Helper Functions for our simple Tasks manager"""

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

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
        if str(config.tools_command) == "make run_robot":
            # Small hack for dev integrated environment: dirty, but it works
            target = f'target_url="{target}"'
    else:
        raise ValueError(f"Unknown job_type_code: {job_type_code}")

    command_str = str(config.tools_command)
    command_parts = command_str.split()

    if config.tools_path:
        # command_parts[0] = str(config.tools_path / command_parts[0])

        #    TODO Small hack for v0.2 in order to simulate a security_check before actually plugging in it
        if command_parts[0].endswith("sleep"):
            # Don't append URL to sleep command
            command = command_parts
        else:
            # When ready, remove if and use only this:
            command = command_parts + [target]

    return command, target


def execute_tool(
    job_id: int, command: list, cwd: str, timeout: int, env_file: str
) -> dict:
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
    # Maybe we have benefit to move this to pydantic at WebApp init
    # Start with minimal env (PATH + basics only)
    tool_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
        "SHELL": os.environ.get("SHELL", "/bin/bash"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    # Load .env only from trusted path
    env_file = Path(env_file)
    if env_file.exists() and env_file.is_file():
        tool_env.update(dotenv_values(str(env_file)))
    # Whitelist ONLY tool-specific keys (customize to your needs)
    allowed_keys = {
        "PATH",
        "HOME",
        "SHELL",
        "LANG",
        "URLCHECKERTOOLS_VIRUSTOTAL_API_KEY",
        "URLCHECKERTOOLS_MISP_URL",
        "URLCHECKERTOOLS_MISP_API_KEY",
        "URLCHECKERTOOLS_LOOKYLOO_URL",
        # Add other tool-specific keys here
    }
    # Filter out any unexpected keys
    for key in list(tool_env):
        if key not in allowed_keys:
            del tool_env[key]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
            env=tool_env,
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

    target = result["target"]

    error = execution_result.get("error")
    stderr = execution_result.get("stderr", "")
    stdout = execution_result.get("stdout", "")
    curl_exit_code = execution_result.get("exit_code")

    # This works only by hypothesis we use curl rewording only http_code as output. Might get improvement here...
    http_code = stdout.strip()

    # Did test execute properly ?
    # nonzero curl exit code means network / DNS / TLS / connection problem
    # 000 means no HTTP response.
    is_reachable = (
        curl_exit_code == 0 and not error and http_code.isdigit() and http_code != "000"
    )
    # 403 or 404 means reachable but problematic.
    is_healthy = is_reachable and 200 <= int(http_code) < 400

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
        job_error_logs = error or stderr

    log.info(f"Job {job_id}: Reachability={reachability_status}")

    # Build output
    output_data = {
        "is_reachable": is_reachable,
        "is_healthy": is_healthy,
        "target": target,
        "exit_code": curl_exit_code,
        "stdout": stdout[:1000],  # Limit size
        "stderr": stderr[:500],
    }

    # Create Result recordexecution_result
    result_record = Result(
        job_id=job_id,
        synthesis=json.dumps(output_data, separators=(",", ":")),
        raw_error=stderr,
        raw_output=stdout,
        validity_status=None,
        reachability_status=reachability_status,
        security_status=None,
    )
    return job_status, job_error_logs, result_record


def _parse_tool_output(stdout: str) -> dict | None:
    """
    Extract the synthesis JSON block from url-checker-tools mixed stdout.
    Specifically looks for the block containing the 'synthesis' key.
    """
    if not stdout or not stdout.strip():
        return None

    decoder = json.JSONDecoder()
    lines = stdout.split("\n")

    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            candidate = "\n".join(lines[i:])
            try:
                obj, _ = decoder.raw_decode(candidate.strip())
                if "synthesis" in obj:  # ← target specifically synthesis block
                    return obj
            except json.JSONDecodeError:
                continue

    log.error(
        {
            "action": "_parse_tool_output",
            "message": "_parse_tool_output: No synthesis JSON block found",
        }
    )
    return None


def handle_security_success(job_id: int, result: dict, execution_result: dict):
    """
    Handle Job3 (Security) success - parse JSON security output

    Must be run from within the FlaskApp context
    """

    stdout = execution_result["stdout"]
    stderr = execution_result["stderr"]

    # Try to parse JSON output from security tool
    # url-checker-tools outputs mixed plain text + JSON blocks,
    # so we extract the last JSON block (synthesis result)
    security_result_json = _parse_tool_output(stdout)
    if security_result_json is None:
        log.error(f"Job {job_id}: Failed to parse JSON output: no JSON block found")
        log.error(f"Job {job_id}: Raw output: {stdout[:500]}")
        security_result_json = {
            "status": "unknown",
            "error": "Failed to parse tool output: no JSON block found",
            "raw_output": stdout[:1000],
            "stderr": stderr[:1000],
        }
    else:
        log.info(f"Job {job_id}: Parsed JSON security result successfully")

    # Parse status (LEVEL 0 is FLAT structure: threat_level directly at root)
    synthesis = security_result_json.get("synthesis", {})
    tool_status = str(synthesis.get("threat_level", "unknown")).lower()

    job_error_logs = ""
    if tool_status in ("safe", "low", "minimal"):
        security_status = SecurityStatus.SAFE.value
        job_status = JobStatus.SUCCESS.value
    elif tool_status in (
        "suspicious",
        "unsafe",
        "high",
        "malicious",
        "critical",
        "medium",
    ):
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
            "error", f"Security check inconclusive (status: {tool_status})"
        )

    log.info(f"Job {job_id}: Security status={security_status}")

    # Create Result record
    result_record = Result(
        job_id=job_id,
        synthesis=json.dumps(security_result_json, separators=(",", ":"))[
            :5000
        ],  # Store JSON, limit size
        raw_output=stdout,
        raw_error=stderr,
        validity_status=None,
        reachability_status=None,
        security_status=security_status,
    )
    return job_status, job_error_logs, result_record

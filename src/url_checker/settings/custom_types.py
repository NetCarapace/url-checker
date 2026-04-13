from pathlib import Path
from typing import Dict

from pydantic import BaseModel


class JobTypeConfig(BaseModel):
    """Configuration for a single job type"""

    tools_path: Path
    tools_command: Path
    tools_env_file: Path | None = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5

    def to_dict(self) -> Dict:
        """
        Convert to JSON-serializable dictionary.
        Converts Path objects to strings.
        """
        return {
            "tools_path": str(self.tools_path),
            "tools_command": str(self.tools_command),
            "tools_env_file": str(self.tools_env_file),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
        }


class JobTypesConfig(BaseModel):
    """
    Job type configurations.

    Environment variable override example:
        URLCHECKER_JOB_TYPES_CONFIG__VALIDATION__TIMEOUT_SECONDS=20

    JSON file format:
        {
            "job_types_config": {
                "VALIDATION_CHECK": {
                    "tools_path": "/usr/bin",
                    "tools_command": "...",
                    "timeout_seconds": 10
                }
            }
        }
    """

    VALIDATION_CHECK: JobTypeConfig = JobTypeConfig(
        tools_path=Path("/usr/bin"),
        tools_command=Path("python3 -m url_checker.helpers.validators.url_validator"),
        tools_env_file=Path(""),
        timeout_seconds=10,
    )

    REACHABILITY_CHECK: JobTypeConfig = JobTypeConfig(
        tools_path=Path("/usr/bin"),
        tools_command=Path("ping -c 3 -W 5"),
        tools_env_file=Path(""),
        timeout_seconds=15,
    )

    SECURITY_CHECK: JobTypeConfig = JobTypeConfig(
        # TODO Small hack for v0.2 in order to simulate a security_check before actually plugging in it
        tools_path=Path("/usr/bin"),
        tools_command=Path("sleep 30"),
        tools_env_file=Path("/etc/url-checker-tools/.env"),
        # When ready, use this instead:
        # tools_path=Path("/usr/share/url-checker-tools"),
        # tools_command=Path("make run_robot"),
        timeout_seconds=60,
    )

    def get(self, job_type_code: str) -> JobTypeConfig:
        """Get config for a job type by code"""
        return getattr(self, job_type_code)

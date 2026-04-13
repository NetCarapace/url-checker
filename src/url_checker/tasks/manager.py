"""
Celery task manager for URL analysis jobs.

Job Flow (associated with views.py/urls[new_url()] POST endpoint):
- Job1 (Validation): Run synchronously in Flask request
- Job2 (Reachability): Run async in a workflow chain that was created only if Job1 succeeds AND URL is HTTPx
- Job3 (Security): Run async after Job2 in the workflow chain, only if Job2 succeeds
"""

from datetime import datetime, timezone

from celery import chain

# Avoid circular import by not importing from app.py
from url_checker.create_apps import celery_app, flask_app
from url_checker.database import sql_db_conn as db

#
from url_checker.helpers.logging import log
from url_checker.main.enums import (
    JobStatus,
    JobTypeCode,
)
from url_checker.main.models import (
    Job,
)
from url_checker.tasks.helpers import build_command, execute_tool


def create_analysis_chain(analysis_id):
    """
    Create 2-jobs Celery chain: Ping → Security Check

    Returns:
        tuple: (job2, job3, workflow)
    """
    # Create Job2 - Ping/Reachability
    job2 = Job(
        analysis_id=analysis_id,
        type_code=JobTypeCode.REACHABILITY_CHECK.value,
        status=JobStatus.PENDING.value,
    )
    job2.add_to_db(False)

    # Create Job3 - HTTP Security Check
    job3 = Job(
        analysis_id=analysis_id,
        type_code=JobTypeCode.SECURITY_CHECK.value,
        status=JobStatus.PENDING.value,
    )
    job3.add_to_db(False)

    # Build chain: Job1 → Job2 → Job3
    workflow = chain(
        job_executor.si(
            job_id=job2.id
        ),  # si to make the signature call immutable and not add results
        job_executor.si(
            job_id=job3.id
        ),  # si to make the signature call immutable and not add results
    )

    return job2, job3, workflow


@celery_app.task(bind=True, max_retries=3)
# We need the previous_result=None to deal with the case of Job3 being passed results from Job2
# even if we do not process it
def job_executor(self, job_id: int = None):
    """
    A Unified job executor for Job2 (Reachability) and Job3 (Security).

    Execution logic branches based on job_type_code.
    Result parsing is handled in the success signal handler with the same logic branching idea.
    """
    log.info(f"Starting job_executor for Job {job_id}")

    # Get job and its type configuration
    with flask_app.app_context():
        job = Job._get(id=job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job_type_code = job.type_code
        url_normalized = job.analysis.url.name

        # Update job to STARTED
        job.status = JobStatus.STARTED.value
        job.start_utc = datetime.now(timezone.utc)
        db.session.commit()

        log.info(f"Job {job_id}: Type={job_type_code}, URL={url_normalized}")

    self.update_state(
        state=JobStatus.STARTED.value, meta={"status": f"Running {job_type_code}"}
    )

    # Get job configuration and prepare excution command
    job_type_enum = JobTypeCode(job_type_code)
    config = job_type_enum.get_config()

    command, target = build_command(job_type_code, config, url_normalized)

    # Execute command
    execution_result = execute_tool(
        job_id=job_id,
        command=command,
        cwd=config.tools_path,
        timeout=config.timeout_seconds,
        env_file=config.tools_env_file,
    )

    # Too premature
    # with flask_app.app_context():
    #     job.status = JobStatus.SUCCESS.value
    #     job.end_utc = datetime.now(timezone.utc)
    #     db.session.commit()

    log.info(f"Job {job_id} executor completed")

    # Return raw results for signal handler to parse
    return {
        "job_id": job_id,
        "job_type_code": job_type_code,
        "target": target,
        "execution_result": execution_result,
    }

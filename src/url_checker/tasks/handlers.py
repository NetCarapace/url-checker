"""Signal handlers for our simple Tasks manager"""

from datetime import datetime, timezone

from celery.signals import task_success

# Avoid circular import by not importing from app.py
from url_checker.create_apps import flask_app
from url_checker.database import sql_db_conn as db
from url_checker.helpers.logging import log
from url_checker.main.enums import JobStatus, JobTypeCode
from url_checker.main.models import (
    Job,
)
from url_checker.tasks.helpers import (
    handle_reachability_success,
    handle_security_success,
)
from url_checker.tasks.manager import job_executor


@task_success.connect(sender=job_executor)
def job_executor_success_handler(sender=None, result=None, **kwargs):
    """
    Parse results based on job_type_code and update database.

    This handler branches based on job type to interpret the raw execution results.
    """
    if not result or "job_id" not in result:
        log.warning("Success handler: No job_id in result")
        return

    job_id = result["job_id"]
    job_type_code = result["job_type_code"]
    execution_result = result["execution_result"]

    log.info(f"Success handler: Processing Job {job_id} (Type: {job_type_code})")

    # Signals have not automatic access to app context, unlikely to Tasks
    with flask_app.app_context():
        job = Job._get(id=job_id)
        if not job:
            log.error(f"Success handler: Job {job_id} not found")
            return

        # Update Job status
        job.status = JobStatus.SUCCESS.value
        job.end_utc = result.get("end_utc") or datetime.now(timezone.utc)
        log.info(f"Job {job_id} marked as COMPLETED")

        url_entry = job.analysis.url

        # If branch based on job type
        if job_type_code == JobTypeCode.REACHABILITY_CHECK.value:
            job_status, job_error_logs, result_record = handle_reachability_success(
                job_id, result, execution_result
            )
        elif job_type_code == JobTypeCode.SECURITY_CHECK.value:
            job_status, job_error_logs, result_record = handle_security_success(
                job_id, result, execution_result
            )
        else:
            log.error(f"Success handler: Unknown job_type_code: {job_type_code}")
            return

        job.status = job_status
        job.error_logs = job_error_logs
        job.update_db(False)
        result_record.add_to_db(False)

        # If this is Job3 (Security Check), mark analysis as complete
        if job_type_code == JobTypeCode.SECURITY_CHECK.value:
            url_entry.last_completed_analysis_id = job.analysis_id
            url_entry.last_completed_analysis_utc = datetime.now(timezone.utc)
            url_entry.analysis_in_progress = False
            url_entry.update_db(False)
            log.info(f"Analysis {job.analysis_id} marked as complete")

        db.session.commit()
        log.info(f"Job {job_id} success handler completed")


@task_success.connect(sender=job_executor)
def job_executor_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Update job executor failures when task fails"""

    # Get job_id from task kwargs
    task_kwargs = kwargs.get("kwargs", {})

    if "job_id" not in task_kwargs:
        log.warning("Failure handler: No job_id in task kwargs")
        return

    job_id = task_kwargs["job_id"]

    log.error(f"Failure handler: Job {job_id} failed: {exception}")

    # Signals have not automatic access to app context, unlikely to Tasks
    with flask_app.app_context():
        job = Job._get(id=job_id)
        if not job:
            log.error(f"Failure handler: Job {job_id} not found")
            return

        job.status = JobStatus.FAILED.value
        job.error_logs = str(exception)
        job.end_utc = datetime.now(timezone.utc)
        job.update_db(False)

        # Mark analysis as no longer in progress:
        # - Job3 failed means no security analysis
        # - Job2 failed means no possibility to trigger Job3
        url_entry = job.analysis.url
        url_entry.analysis_in_progress = False
        url_entry.update_db(False)

        db.session.commit()

        log.info(
            f"Job {job_id} marked as FAILED, URL shows now no analysis in progress"
        )


@task_success.connect(sender=job_executor)
def job_executor_retry_handler(sender=None, reason=None, **kwargs):
    """Update job executor tasks retries"""

    task_kwargs = kwargs.get("kwargs", {})

    if "job_id" not in task_kwargs:
        return

    job_id = task_kwargs["job_id"]

    log.warning(f"Retry handler: Job {job_id} is retrying: {reason}")

    with flask_app.app_context():
        job = Job._get(id=job_id)
        if not job:
            return

        job.status = JobStatus.RETRY.value
        if job.error_logs:
            job.error_logs += f"\nRetry: {reason}"
        else:
            job.error_logs = f"Retry: {reason}"
        job.update_db()

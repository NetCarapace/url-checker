import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Response, current_app, jsonify, request
from marshmallow import ValidationError

from url_checker.database import sql_db_conn as db
from url_checker.helpers.authentication import require_api_token
from url_checker.helpers.logging import log
from url_checker.main import main
from url_checker.main.enums import (
    JobStatus,
    JobTypeCode,
    ValidityStatus,
)
from url_checker.main.models import URL, Analysis, Job, Result
from url_checker.main.schema import URLValidationSchema
from url_checker.main.validators import validate_url
from url_checker.settings.settings import settings
from url_checker.tasks.manager import create_analysis_chain


@main.route("/", methods=["GET"])
# not protected to keep a test entry point
def hello():
    app_version = current_app.config["VERSION"]
    return f"Hello, Restena! URLChecker is running at version {app_version}. URLChecker-tools with version XXX."


@main.route("/openapi.yaml", methods=["GET"])
# not protected to keep doc easily accessible
def get_openapi_yaml():
    """Serve the OpenAPI YAML specification file"""
    try:
        # Get the project root directory (where static/ folder is)
        # Assuming structure: project_root/static/openapi.yaml
        project_root = settings.BASE_DIR
        static_folder = Path(os.path.join(project_root, "static"))
        yaml_path = static_folder / "openapi.yaml"

        # Read and return with text/plain mimetype to display in browser
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()

        return Response(
            yaml_content,
            mimetype="text/plain; charset=utf-8",  # ✅ Display in browser
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                # ✅ Remove this if you don't want download behavior:
                # 'Content-Disposition': 'attachment; filename=openapi.yaml'
            },
        )
    except FileNotFoundError:
        return jsonify({"error": "OpenAPI specification not found"}), 404


###
# URLS
###########
@main.route("/urls/all", methods=["GET", "DELETE"])
@require_api_token
def all_urls():
    if request.method == "GET":
        urls = URL.get_all()
        response = {"urls": [url.to_dict() for url in urls]}
        return jsonify(response), 200
    else:
        num_deleted = URL.delete_all_from_table()
        return jsonify({"message": f"{num_deleted} urls deleted"}), 200


@main.route("/urls", methods=["POST"])
@require_api_token
def new_url():
    """
    POST endpoint to create a new URL analysis and the associated object in database.

    Flow:
    1. Validate input with Marshmallow schema
    2. Create URL and Analysis entries
    3. Run Job1 (Validation) synchronously
    4. If valid, create and start Job2+Job3 chain asynchronously
    5. Return response with analysis ID and job IDs
    """
    payload = request.get_json()
    if not payload or "url" not in payload:
        return (
            jsonify({"error": "Data payload empty or missing required field: url"}),
            400,
        )
    url = payload.get("url")
    if not isinstance(url, str):
        return jsonify({"error": "url must be a string"}), 400
    if len(url) > settings.url["max_length"]:
        return (
            jsonify(
                {
                    "error": f"url string length must be less or equal than {settings.url['max_length']}"
                }
            ),
            400,
        )

    # Step 1: Quick first validation input with Marshmallow (Job1)
    # -> early escape
    schema = URLValidationSchema()
    try:
        data = schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({"error": "Invalid URL", "details": e.messages}), 400

    url_normalized = data["url"]

    # Create URL entry if not exists
    exist_url_entry = URL.get_by_name_or_uuid(name=url)
    if not exist_url_entry:
        url_uuid = str(uuid4())
        while URL.get_by_name_or_uuid(uuid=url_uuid) is not None:
            url_uuid = str(uuid4())

        url_entry = URL(
            name=url,
            normalized=url_normalized,
            uuid=url_uuid,
        )
        url_entry.add_to_db(False)
    else:
        url_entry = exist_url_entry

    url_entry.analysis_in_progress = True
    url_entry.update_db()

    # Initialize to None the jobs skipped when scheme is not httpx
    job2 = None
    job3 = None

    try:
        # Step 3: Create Analysis
        analysis = Analysis(
            url_id=url_entry.id,
            datetime_utc=datetime.now(timezone.utc),
        )
        analysis.add_to_db(False)

        # Step 4: Create Job1 (Validation)
        job1 = Job(
            analysis_id=analysis.id,
            type_code=JobTypeCode.VALIDATION_CHECK.value,
            status=JobStatus.PENDING.value,
        )
        job1.add_to_db(False)

        log.info(
            f"Created Analysis {analysis.id} with Job1 {job1.id} for URL {url_entry.uuid}"
        )

        # Step 5: Run Job1 synchronously (immediate validation)
        job1.status = JobStatus.STARTED.value
        job1.start_utc = datetime.now(timezone.utc)

        log.info(f"Running Job1 {job1.id} synchronously...")

        # Perform validation
        validation_result = validate_url(url)

        # Create result
        result = Result(
            job_id=job1.id,
            output=str(validation_result.details),
            validity_status=validation_result.validity_status,
            reachability_status="",
            security_status="",
        )
        result.add_to_db(False)

        # Update job1
        job1.end_utc = datetime.now(timezone.utc)

        if validation_result.is_valid:
            job1.status = JobStatus.SUCCESS.value
            log.info(
                f"Job1 {job1.id} completed successfully: {validation_result.validity_status}"
            )
        else:
            job1.status = JobStatus.FAILED.value
            job1.error_logs = validation_result.error_message or "Validation failed"
            log.warning(f"Job1 {job1.id} failed: {validation_result.error_message}")

        # Step 6: If valid, create and start Job2+Job3 chain
        if validation_result.is_valid:
            # Check if it's HTTP (only HTTP URLs get reachability + security checks)
            if validation_result.validity_status == ValidityStatus.VALID_HTTP.value:
                log.info("URL is valid HTTP, creating Job2+Job3 chain...")

                # Create and start chain asynchronously
                job2, job3, workflow = create_analysis_chain(analysis.id)
        db.session.commit()
    except Exception as e:
        # All Jobs and Analysis that were in the process of creation are not destroyed
        # and never commited to database
        db.session.rollback()
        # We manually revert the boolean due to abortion of analysis
        url_entry.analysis_in_progress = False
        url_entry.update_db()
        #
        log.error(f"Error creating URL analysis: {e}")
        return (
            jsonify(
                {"error": "Internal server error. Analysis aborted.", "message": str(e)}
            ),
            500,
        )

    if validation_result.is_valid:
        # Check if it's HTTP (only HTTP URLs get reachability + security checks)
        if validation_result.validity_status == ValidityStatus.VALID_HTTP.value:
            # Important to commit before launching the independant workflow
            # A crash in the workflow will be treated differently, the objects in database case persist
            # with Failure status for example
            workflow.apply_async()
            log.info(f"Started async chain: Job2 {job2.id} -> Job3 {job3.id}")
        else:
            log.info("URL is valid but non-HTTP, skipping Job2+Job3 - No results")
    else:
        # We do not even need to mark Job2 and Job3 as skipped because they were never created
        log.info("URL is invalid, skipping Job2+Job3")

    # Step 7: Build response
    response = {
        "url_name": url_entry.name,
        "url_uuid": url_entry.uuid,
        "analysis": {
            "id": analysis.id,
            "created_at_utc": analysis.datetime_utc.isoformat(),
        },
        "jobs": {
            "job1_validation": {
                "id": job1.id,
                "type_code": job1.type_code,
                "status": job1.status,
                "validity_status": validation_result.validity_status,
                "is_valid": validation_result.is_valid,
            },
            "job2_reachability": {
                "id": job2.id if job2 else None,
                "type_code": (
                    job2.type_code if job2 else JobTypeCode.REACHABILITY_CHECK.value
                ),
                "status": job2.status if job2 else JobStatus.SKIPPED.value,
            },
            "job3_security": {
                "id": job3.id if job3 else None,
                "type_code": (
                    job3.type_code if job2 else JobTypeCode.SECURITY_CHECK.value
                ),
                "status": job3.status if job3 else JobStatus.SKIPPED.value,
            },
        },
        "message": (
            "Analysis created" if validation_result.is_valid else "URL is invalid"
        ),
    }

    return jsonify(response), 201


@main.route("/urls/<uuid>", methods=["GET", "DELETE"])
@require_api_token
def one_url(uuid):
    """GET endpoint to get URL status summary"""
    url = URL.get_by_name_or_uuid(uuid=uuid)
    if not url:
        return jsonify({"error": "URL not known"}), 404

    if request.method == "GET":
        try:
            response = url.to_dict()

        except Exception as e:
            log.error(f"Error fetching URL status: {e}")
            return jsonify({"error": "Internal server error", "message": str(e)}), 500
    else:
        url.delete_from_db()
        response = {"message": "URL deleted"}

    return jsonify(response), 200


###
# ANALYSES
###########
@main.route("/analyses/all", methods=["GET", "DELETE"])
@require_api_token
def all_analyses():
    if request.method == "GET":
        analyses = Analysis.get_all()
        response = {"jobs": [analysis.to_dict() for analysis in analyses]}
        return jsonify(response), 200
    else:
        num_deleted = Analysis.delete_all_from_table()
        return jsonify({"message": f"{num_deleted} analyses deleted"}), 200


@main.route("/analyses/<analysis_id>", methods=["GET", "DELETE"])
@require_api_token
def one_analysis(analysis_id):
    """GET endpoint to check analysis status"""
    analysis = Analysis._get(id=analysis_id)
    if not analysis:
        return jsonify({"error": "Analysis not found"}), 404

    if request.method == "GET":
        response = {
            "validity_status": analysis.get_validity_status(),
            "reachability_status": analysis.get_reachability_status(),
            "security_status": analysis.get_security_status(),
            "overall_status": analysis.overall_status,
            "data": analysis.to_dict(),
        }
    else:
        Analysis.delete_from_db()
        response = {"message": "Analysis deleted"}

    return jsonify(response), 200


###
# JOBS
###########
@main.route("/jobs/all", methods=["GET", "DELETE"])
@require_api_token
def all_jobs():
    if request.method == "GET":
        jobs = Job.get_all()
        response = {"jobs": [job.to_dict() for job in jobs]}
    else:
        num_deleted = Job.delete_all_from_table()
        response = {"message": f"{num_deleted} jobs deleted"}

    return jsonify(response), 200


@main.route("/jobs/<job_id>", methods=["GET", "DELETE"])
@require_api_token
def one_job(job_id):
    job = Job._get(id=job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if request.method == "GET":
        analysis = job.analysis
        result = job.result
        response = {
            "job_id": job.id,
            "url_id": analysis.url_id if analysis else None,
            "status": job.status,
            "result": result.output if result else None,
            "error": job.error_logs,
            "start_utc": (job.start_utc.isoformat() if job.start_utc else None,),
            "end_utc": (job.end_utc.isoformat() if job.end_utc else None,),
        }
    else:
        Job.delete_from_db()
        response = {"message": "Job deleted"}

    return response, 200


###
# RESULTS
###########
@main.route("/results/all", methods=["GET", "DELETE"])
@require_api_token
def all_results():
    if request.method == "GET":
        results = Result.get_all()
        response = {"results": [result.to_dict() for result in results]}
        return jsonify(response), 200
    else:
        num_deleted = Result.delete_all_from_table()
        # We leave Flask handle the error propagation
        # Alternative kept for legacy if we need it one day:
        # try:
        #     deleted_count = Result.delete_all_from_table()
        #     return jsonify({"message": f"{deleted_count} results deleted"}), 200
        # except SQLAlchemyError:
        #     return jsonify({"error": "Failed to delete results"}), 500
        return jsonify({"message": f"{num_deleted} results deleted"}), 200


@main.route("/results/<result_id>", methods=["GET", "DELETE"])
@require_api_token
def one_result(result_id):
    result = Result._get(id=result_id)
    if not result:
        return jsonify({"error": "Result not found"}), 404

    if request.method == "GET":
        response = result.to_dict()
    else:
        Result.delete_from_db()
        response = {"message": "Job deleted"}

    return response, 200

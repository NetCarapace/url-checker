from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from url_checker.app import app as flask_app
from url_checker.models import Job, db


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
    flask_app.config["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/0"

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def test_submit_job(client):
    """Test submitting a job."""
    response = client.post(
        "/jobs", json={"url_id": "test123", "url": "https://example.com"}
    )
    assert response.status_code == 200
    assert "job_id" in response.json
    assert response.json["status"] == "pending"


def test_submit_job_missing_data(client):
    """Test submitting a job with missing data."""
    response = client.post("/jobs", json={"url": "https://example.com"})
    assert response.status_code == 400
    assert "error" in response.json


def test_get_job_status(client):
    """Test getting the status of a job."""
    # Create a test job
    with flask_app.app_context():
        job = Job(
            job_id="test-job-id",
            url_id="test123",
            status="completed",
            creation_timestamp=datetime.now(),
        )
        db.session.add(job)
        db.session.commit()

    response = client.get("/jobs/test-job-id")
    assert response.status_code == 200
    assert response.json["job_id"] == "test-job-id"
    assert response.json["status"] == "completed"


def test_get_nonexistent_job(client):
    """Test getting the status of a non-existent job."""
    response = client.get("/jobs/nonexistent-job-id")
    assert response.status_code == 404
    assert "error" in response.json


@patch("url_analyzer.tasks.celery.send_task")
def test_job_submission_enqueues_task(mock_send_task, client):
    """Test that submitting a job enqueues a Celery task."""
    mock_send_task.return_value = MagicMock(id="mock-task-id")

    response = client.post(
        "/jobs", json={"url_id": "test123", "url": "https://example.com"}
    )

    assert response.status_code == 200
    mock_send_task.assert_called_once_with(
        "url_analyzer.tasks.analyze_url", args=["test123", "https://example.com"]
    )

#!/usr/bin/env python3
"""Main Module.

This modules provide the Flask-SQLAlchemy database Models for Main.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import sqlalchemy as sql_alc
import sqlalchemy.orm as sql_orm

from url_checker.database import sql_db_conn as db
from url_checker.helpers.custom_types import UTCDateTime
from url_checker.main.enums import (
    JobStatus,
    JobTypeCode,
    ReachabilityStatus,
    SecurityStatus,
    ValidityStatus,
)
from url_checker.models import Base


class URL(Base):
    __tablename__ = "urls"
    # TODO Align the length depending on constraints from providers and webserver
    # Should be consistent with what we accept on edu.lu
    name: sql_orm.Mapped[str] = sql_orm.mapped_column(
        # TODO replace hardcoding my settings value
        sql_alc.Text,
        nullable=False,
    )
    normalized: sql_orm.Mapped[str] = sql_orm.mapped_column(
        # TODO replace hardcoding my settings value
        sql_alc.Text,
        nullable=False,
    )
    #
    uuid: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.String(36),
        nullable=False,
        unique=True,
    )

    # Last cached statuses (atomically updated by jobs)
    # It means that if new analysis is in progress, we returns the old statuses
    last_completed_analysis_id: sql_orm.Mapped[Optional[int]] = sql_orm.mapped_column(
        sql_alc.Integer, nullable=True
    )
    last_completed_analysis_utc: sql_orm.Mapped[Optional[datetime]] = (
        sql_orm.mapped_column(UTCDateTime, nullable=True)
    )
    # To provide the requester the information about "does fresh status is incomming"
    # Can also be used to manually lock for no concurrent analyses
    analysis_in_progress: sql_orm.Mapped[bool] = sql_orm.mapped_column(
        sql_alc.Boolean, default=False, nullable=False
    )

    # one-to-many on the one side
    # i.e. one FieldType can have many Field instances.
    analyses = sql_orm.relationship(
        "Analysis",
        back_populates="url",
        cascade="all, delete",  # Deleting one URL should delete all related Jobs
    )

    # Version column for optimistic locking
    version: sql_orm.Mapped[int] = sql_orm.mapped_column(
        sql_alc.Integer, default=0, nullable=False
    )

    # SQLAlchemy 2.0 automatic version tracking
    __mapper_args__ = {
        "version_id_col": version,
    }

    # Computed properties
    @property
    def last_validity_status(self) -> Tuple:
        """Get the status from the most recent result of the last completed job"""
        last_validity_status = None
        if self.last_completed_analysis_id is not None:
            last_completed_analysis_id = self.last_completed_analysis_id

            analysis = Analysis._get(id=last_completed_analysis_id)
            last_validity_status = analysis.get_validity_status()

        return last_validity_status

    @property
    def last_reachability_status(self) -> Tuple:
        """Get the status from the most recent result of the last completed job"""
        last_reachability_status = None
        if self.last_completed_analysis_id is not None:
            last_completed_analysis_id = self.last_completed_analysis_id

            analysis = Analysis._get(id=last_completed_analysis_id)
            last_reachability_status = analysis.get_reachability_status()

        return last_reachability_status

    @property
    def last_security_status(self) -> Tuple:
        """Get the status from the most recent result of the last completed job"""
        last_security_status = None
        if self.last_completed_analysis_id is not None:
            last_completed_analysis_id = self.last_completed_analysis_id

            analysis = Analysis._get(id=last_completed_analysis_id)
            last_security_status = analysis.get_security_status()

        return last_security_status

    @property
    def last_overall_status(self) -> str:
        """
        Compute overall status from cached columns
        Hierarchy: INVALID > UNREACHABLE > UNSAFE > SAFE > UNKNOWN
        """
        last_overall_status = None
        if self.last_completed_analysis_id is not None:
            last_completed_analysis_id = self.last_completed_analysis_id

            analysis = Analysis._get(id=last_completed_analysis_id)
            last_overall_status = analysis.overall_status

        return last_overall_status

    # Private methods

    # Public methods
    @classmethod
    def get_by_name_or_uuid(cls, name: str = None, uuid: str = None):
        if uuid is not None:
            url_entry = db.session.execute(
                db.select(
                    cls,
                ).where(
                    cls.uuid == uuid,
                )
            ).scalar_one_or_none()
        else:
            url_entry = db.session.execute(
                db.select(
                    cls,
                ).where(
                    cls.name == name,
                )
            ).scalar_one_or_none()

        return url_entry

    # atomic update method (no commit)
    def update_from_completed_analysis(
        self,
        analysis_id: int,
    ) -> None:
        """
        Atomically update URL status from completed analysis onward.
        This include the turning to False the analysis_in_progress.

        This should be called within a transaction that also updated the last Job of the
        chain create for the Analysis to status to COMPLETED.

        Args:
            analysis_id: The analysis that just completed
        """
        # All updates in one assignment block (atomic within transaction)
        # But for other Race conditions, SQLAlchemy automatically handles version checking
        # If version changed, StaleDataError is raised
        self.last_completed_analysis_id = analysis_id
        self.last_completed_analysis_utc = datetime.now(timezone.utc)
        self.analysis_in_progress = False

    def get_status_info(self, status_value: str, enum_class) -> Dict:
        """
        Helper to get full status info (code, label, description)
        Returns dict with None values if status_value is None
        """
        if status_value is None:
            return {
                "code": None,
                "label": "Unknown",
                "description": None,
            }

        return {
            "code": status_value,
            "label": enum_class.get_label(status_value),
            "description": enum_class.get_description(status_value),
        }

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "uuid": str(self.uuid),
            "last_status": {
                "overall": self.last_overall_status,
                "validity": self.get_status_info(
                    self.last_validity_status, ValidityStatus
                ),
                "reachability": self.get_status_info(
                    self.last_reachability_status, ReachabilityStatus
                ),
                # Best Word I could find that is also a known (malicious is adjective)
                "security": self.get_status_info(
                    self.last_security_status, SecurityStatus
                ),
            },
            "last_completed_analysis": {
                "id": self.last_completed_analysis_id,
                "utc": (
                    self.last_completed_analysis_utc.isoformat()
                    if self.last_completed_analysis_utc
                    else None
                ),
            },
            "analysis_in_progress": self.analysis_in_progress,
            "analyses_ids": [analysis.id for analysis in self.analyses],
        }


class Analysis(Base):
    __tablename__ = "analyses"

    datetime_utc: sql_orm.Mapped[datetime | None] = sql_orm.mapped_column(
        UTCDateTime,
        nullable=True,
        default=None,
    )
    # one-to-many on the one side
    # i.e. one FieldType can have many Field instances.
    jobs = sql_orm.relationship(
        "Job",
        back_populates="analysis",
        cascade="all, delete",  # Deleting one URL should delete all related Jobs
    )
    # many-to-one on the many side
    url_id: sql_orm.Mapped[int] = sql_orm.mapped_column(
        sql_alc.ForeignKey("urls.id"),
    )
    url = sql_orm.relationship(
        "URL",
        back_populates="analyses",
    )

    @property
    def overall_status(self) -> str:
        """
        Compute overall status from all jobs in this analysis.

        Hierarchy: INVALID > UNREACHABLE > UNSAFE > SAFE > UNKNOWN

        Returns:
            Human-readable status label
        """

        # Check validity first
        if self.get_validity_status() == ValidityStatus.INVALID.value:
            return ValidityStatus.INVALID.label

        # Check reachability
        if self.get_reachability_status() == ReachabilityStatus.UNREACHABLE.value:
            return ReachabilityStatus.UNREACHABLE.label

        # Check security
        if self.get_security_status() == SecurityStatus.UNSAFE.value:
            return SecurityStatus.UNSAFE.label
        if self.get_security_status() == SecurityStatus.SAFE.value:
            return SecurityStatus.SAFE.label

        # Default to unknown
        return SecurityStatus.UNKNOWN.label

    # Private methods
    def _get_job_by_type_code(self, job_type_code):
        if not self.jobs:
            return
        # Should be fine as we have ony one job of type_code for each analysis
        job = [job for job in self.jobs if job.type_code == job_type_code][0]
        return job

    # Public methods
    def get_validity_status(self):
        job = self._get_job_by_type_code(JobTypeCode.VALIDATION_CHECK.value)
        return job.result.validity_status if job.result is not None else None

    def get_reachability_status(self):
        job = self._get_job_by_type_code(JobTypeCode.REACHABILITY_CHECK.value)
        return job.result.reachability_status if job.result is not None else None

    def get_security_status(self):
        job = self._get_job_by_type_code(JobTypeCode.SECURITY_CHECK.value)
        return job.result.security_status if job.result is not None else None

    def to_dict(self):
        # TODO use the jobs.dict
        jobs_data = []
        for job in self.jobs:
            job_data = {
                "id": job.id,
                "job_type": {
                    "code": job.type_code,
                    "label": JobTypeCode(job.type_code).label,
                },
                "status": job.status,
                "started_at": job.start_utc.isoformat() if job.start_utc else None,
                "completed_at": job.end_utc.isoformat() if job.end_utc else None,
            }
            jobs_data.append(job_data)

        return {
            "analysis_id": self.id,
            "url_id": self.url.id,
            "url": self.url.name if self.url else None,
            "uuid": self.url.uuid if self.url else None,
            "datetime_utc": (
                self.datetime_utc.isoformat() if self.datetime_utc else None,
            ),
            "jobs_id": [job.id for job in self.jobs] if self.jobs else [],
            "jobs_data": jobs_data,
        }


class Job(Base):
    __tablename__ = "jobs"

    # JobStatus values
    # Remember it is different from Celery task status which are: STARTED / PROCESSING / RETRY / COMPLETED / FAILURE
    status: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.String(32),
        nullable=False,
        default=JobStatus.PENDING.value,
    )
    #
    start_utc: sql_orm.Mapped[datetime | None] = sql_orm.mapped_column(
        UTCDateTime,
        nullable=True,
        default=None,
    )
    end_utc: sql_orm.Mapped[datetime | None] = sql_orm.mapped_column(
        UTCDateTime,
        nullable=True,
        default=None,
    )
    error_logs: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.Text,
        default="",
        nullable=False,
    )

    # many-to-one on the many side
    analysis_id: sql_orm.Mapped[int] = sql_orm.mapped_column(
        sql_alc.ForeignKey("analyses.id"),
    )
    analysis = sql_orm.relationship(
        "Analysis",
        back_populates="jobs",
    )

    # one-to-one on the one side
    type_code: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.String(24),
        nullable=False,
    )

    result = sql_orm.relationship(
        "Result",
        back_populates="job",
        cascade="all, delete",  # Deleting one URL should delete all related Jobs
        uselist=False,  # Make it a "real" one-to-one and avoid the List pitfall
    )

    # Computed properties
    @property
    def is_completed(self) -> bool:
        """Check if this Job instance has completed"""
        return self.status in [
            JobStatus.SUCCESS.value,
            JobStatus.FAILED.value,
            JobStatus.SKIPPED.value,
        ]

    @property
    def is_active(self) -> bool:
        """Check if this job is still running"""
        return self.status in [
            JobStatus.PENDING.value,
            JobStatus.STARTED.value,
            JobStatus.RETRY.value,
        ]

    @property
    def was_skipped(self) -> bool:
        """Check if this job was skipped"""
        return self.status == JobStatus.SKIPPED.value

    @property
    def is_successful(self) -> bool:
        """Check if this job completed successfully"""
        return self.status == JobStatus.SUCCESS.value

    @property
    def has_failed(self) -> bool:
        """Check if this job failed"""
        return self.status == JobStatus.FAILED.value

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds"""
        if self.start_utc and self.end_utc:
            return (self.end_utc - self.start_utc).total_seconds()
        return None

    @property
    def full_type_code(self) -> JobTypeCode:
        """Get job type enum from stored code"""
        return JobTypeCode(self.type_code)

    # Private methods

    # Public methods
    def __repr__(self):
        status_label = JobStatus.get_label(self.status)
        # Add state indicators
        if self.is_completed:
            state = "[completed]"
        elif self.is_active:
            state = "[active]"
        else:
            state = "[unknown]"
        return f"<Job {self.id} - {self.type_code}: {status_label} {state}>"

    @classmethod
    def get_all_for_analysis_id(cls, url_id: str = None, status: str = None):
        """Get all jobs for an analysis, optionally filtered by status"""
        job = None
        if url_id is not None:
            if status is None:
                job = db.session.execute(
                    db.select(
                        cls,
                    ).where(
                        cls.analysis.url_id == url_id,
                    )
                ).scalar_one_or_none()
            else:
                job = db.session.execute(
                    db.select(
                        cls,
                    ).where(
                        cls.analysis.url_id == url_id,
                        cls.status == status,
                    )
                ).scalar_one_or_none()
        return job

    def to_dict(self, verbose: bool = False, include_result: bool = False) -> Dict:
        """Serialize job to dictionary"""
        data = {
            "id": self.id,
            "url_id": self.analysis.url_id,
            "analysis_id": self.analysis_id,
            "job_type_config": JobTypeCode.get_config(self.type_code).to_dict(),
            "is_completed": self.is_completed,
            "is_active": self.is_active,
        }
        if verbose:
            data["verbose_status"] = (
                {
                    "value": self.status,
                    "label": JobStatus.get_label(self.status),
                    "description": JobStatus.get_description(self.status),
                    "start_utc": (
                        self.start_utc.isoformat() if self.start_utc else None,
                    ),
                    "end_utc": (self.end_utc.isoformat() if self.end_utc else None,),
                    "duration_seconds": self.duration_seconds,
                    "error_logs": self.error_logs if self.error_logs else None,
                },
            )
        if include_result and self.result:
            # When we have actual results check because maybe we need to unpack
            # to dict here
            data["result"] = self.result.to_dict() if self.result else None

        return data


class Result(Base):
    __tablename__ = "results"

    synthesis: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.Text,
        default="",
        nullable=False,
    )
    raw_error: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.Text,
        default="",
        nullable=False,
    )
    raw_output: sql_orm.Mapped[str] = sql_orm.mapped_column(
        sql_alc.Text,
        default="",
        nullable=False,
    )
    # it should become a many-to-one on the one side
    # We would have job1, job2, job3, output1, output2 and output3
    job_id: sql_orm.Mapped[int] = sql_orm.mapped_column(
        sql_alc.ForeignKey("jobs.id"),
        nullable=False,
    )
    job: sql_orm.Mapped["Job"] = sql_orm.relationship(
        back_populates="result",
    )
    # SAFE / UNSAFE
    # A failed Job means UNSAFE by conservatism
    #
    # This will move to analyses, be renamed malicous: true, false, null
    # and along valid: true/false, reachability: true/false
    #
    # Job 1
    validity_status: sql_orm.Mapped[str | None] = sql_orm.mapped_column(
        sql_alc.String(16), nullable=True
    )
    # Job 2
    reachability_status: sql_orm.Mapped[str | None] = sql_orm.mapped_column(
        sql_alc.String(16), nullable=True
    )
    # Job 3
    security_status: sql_orm.Mapped[str | None] = sql_orm.mapped_column(
        sql_alc.String(16), nullable=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "url_id": self.job.analysis.url_id if self.job.analysis.url_id else None,
            "analysis_id": self.job.analysis_id if self.job.analysis_id else None,
            "job_id": self.job_id,
            "job_type_code": self.job.type_code if self.job else None,
            "analysis_synthesis": self.synthesis,
            "validity_status": self.validity_status,
            "reachability_status": self.reachability_status,
            "security_status": self.security_status,
        }

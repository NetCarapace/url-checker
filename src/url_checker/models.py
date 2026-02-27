#!/usr/bin/env python3
"""URL Checker.

This modules provide the Flask-SQLAlchemy Base Models for all Web Apps.
"""

from datetime import datetime, timezone

import sqlalchemy as sql_alc
import sqlalchemy.orm as sql_orm
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from url_checker.database import sql_db_conn as db
from url_checker.helpers.logging import log


class Base(db.Model):
    """
    The class Base defines the template class for all the URL Checker module classes

         Fields:
              name_index: index based on ids
              id (Integer)                : the id of the user row
              date_created_utc (DateTime) : date of creation of the row (UTC)
              date_modified_utc (DateTime)  : date of modification of the row (UTC)
              id_user_loggedin (Integer): the user id that made last modification to the row
    """

    # To avoid to store that model as a table
    __abstract__ = True

    # Common fields
    id: sql_orm.Mapped[int] = sql_orm.mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    # Note the default function:
    # no brackets so passing the function itself, and not the result of calling it
    date_created_utc: sql_orm.Mapped[datetime] = sql_orm.mapped_column(
        default=lambda: datetime.now(timezone.utc),
    )
    date_modified_utc: sql_orm.Mapped[datetime] = sql_orm.mapped_column(
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
    )
    # The day we have a real user management and RBAC system
    # Facility to register user making the changes or init
    # id_user_loggedin = db.column(db.Integer, index=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)

    # Properties to ease up accesses
    @property
    def db_name(self):
        """Get the database name"""
        return db.engine.url.database

    # Common class methods and properties
    # Private
    @classmethod
    def _get_db_name_cls(cls):
        """Get the database name"""
        return db.engine.url.database

    @classmethod
    def _get(cls, id: int = None):
        """Get one entry"""
        entry = None
        if id is not None:
            entry = db.session.execute(
                db.select(
                    cls,
                ).where(
                    cls.id == id,
                )
            ).scalar_one_or_none()

        return entry

    # Public
    @classmethod
    def get_statistics(cls):
        """A getter method for retrieving basic statics on a table"""
        return {
            "tableName": cls.__tablename__,
            "numberOfRecords": db.session.execute(
                db.select(sql_alc.func.count()).select_from(cls)
            ).scalar(),
        }

    @classmethod
    def delete_all_from_table(cls):
        """Delete all content from the table."""
        num_deleted = 0
        try:
            # Query all records from the table
            records = db.session.execute(db.select(cls)).scalars().all()
            for record in records:
                db.session.delete(record)
            db.session.commit()
            num_deleted = len(records)
            log.info(
                f"All content of table {cls.__tablename__!r} "
                f"deleted in database {cls._get_db_name_cls()!r}"
            )
        except SQLAlchemyError as error:
            log.error(
                f"Error when trying to delete all items of table {cls.__tablename__!r} "
                f"in database {cls._get_db_name_cls()!r}: {error}"
            )
            db.session.rollback()
            raise

        return num_deleted

    @classmethod
    def get_all(cls):
        """Returns a list of rows with all objects"""
        try:
            all_entries = db.session.execute(db.select(cls)).scalars().all()
            log.info(
                f"All content of table {cls.__tablename__!r} "
                f"retrieved from database {cls._get_db_name_cls()!r}"
            )
        except SQLAlchemyError as error:
            log.error(
                f"Error when trying to retrieve data from table {cls.__tablename__!r} "
                f"in database {cls._get_db_name_cls()!r}: {error}"
            )
            raise

        return all_entries

    # Common utility methods
    def add_to_db(self, commit=True):
        """Save an instance of the model to the database, with commit by default."""
        try:
            db.session.add(self)
            if commit:
                db.session.commit()
            else:
                db.session.flush()
            log.info(
                f"New item saved in table {self.__tablename__!r} "
                f"in database {self.db_name!r}"
            )
        except (IntegrityError, SQLAlchemyError) as error:
            log.error(
                f"Error when trying to save items of table {self.__tablename__!r} "
                f"in database {self.db_name!r}: {error}"
            )
            db.session.rollback()
            raise

    def update_db(self, commit=True):
        """Update an instance of the model to the database."""
        try:
            if commit:
                db.session.commit()
            else:
                db.session.flush()
            log.info(
                f"Item updated in table {self.__tablename__!r} "
                f"in database {self.db_name!r}"
            )
        except (IntegrityError, SQLAlchemyError) as error:
            log.error(
                f"Error when trying to update items of table {self.__tablename__!r} "
                f"in database {self.db_name!r}: {error}"
            )
            db.session.rollback()
            raise

    def delete_from_db(self, commit=True):
        """Delete an instance of the model of the database."""
        try:
            db.session.delete(self)
            if commit:
                db.session.commit()
            else:
                db.session.flush()
            log.info(
                f"Item deleted from table {self.__tablename__!r} "
                f"in database {self.db_name!r}"
            )
        except SQLAlchemyError as error:
            log.error(
                f"Error when trying to delete an item of table {self.__tablename__!r} "
                f"in database {self.db_name!r}: {error}"
            )
            db.session.rollback()
            raise

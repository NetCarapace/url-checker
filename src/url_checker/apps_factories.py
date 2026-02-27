"""A dedicated module to reference the application factories used by this web application"""

import logging
import sys

from celery import Celery, Task
from flask import Flask

from url_checker.database import migrate_db, sql_db_conn

# this paths are necessary to make it works also for debian packaging
from url_checker.helpers.logging import init_route_logging


def celery_init_app(app):
    """Initialize Celery with a Flask app context support"""

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs) -> object:
            """Provide the ability to use Flask app_context from within a Celery Task"""
            print(f"FlaskTask called with app: {app}")  # Debug line
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(
        app.name,
        task_cls=FlaskTask,
        broker=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_BACKEND_RESULT"],
        task_ignore_result=True,
        # CELERY_IMPORTS = ['comm.tasks']
    )

    celery_app.set_default()

    celery_app.conf.update(
        task_track_started=True,
        result_extended=True,
    )

    app.extensions["celery"] = celery_app

    return celery_app


def create_flask_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    from url_checker.settings.settings import flask_config

    logging.basicConfig(level=flask_config["LOGLEVEL"])
    logging.info("Settings retrieved")

    flask_app = Flask(__name__, instance_path=flask_config["INSTANCE_PATH"])
    flask_app.config.from_mapping(flask_config)

    # migrate = Migrate(app)
    sql_db_conn.init_app(flask_app)
    # We keep separated code and database migration so we only connect the migrate object here
    # but rely on database scheme creation out of this app
    migrate_db.init_app(flask_app, sql_db_conn)

    # Clear default Flask handlers
    flask_app.logger.handlers.clear()

    # Attach only a single StreamHandler to stdout
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    flask_app.logger.addHandler(handler)

    # Prevent propagation to root logger (avoids duplicate)
    flask_app.logger.propagate = False
    flask_app.logger.setLevel(logging.INFO)

    # Initialize automatic route logging (only active in debug mode)
    init_route_logging(flask_app)

    celery_init_app(flask_app)

    return flask_app

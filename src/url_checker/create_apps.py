"""A dedicated module to create all the application objects to be imported from main and other modules"""

from url_checker.apps_factories import create_flask_app

# Create Flask app and Celery app once
flask_app = create_flask_app()
# celery_app = celery_init_app(flask_app)
celery_app = flask_app.extensions["celery"]

celery_app.conf.update(
    imports=[
        "url_checker.tasks.handlers",
        "url_checker.tasks.helpers",
        "url_checker.tasks.manager",
    ],
)

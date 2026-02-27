"""The main entry point of this Python module package."""

from url_checker.admin import admin  # noqa: E402
from url_checker.create_apps import celery_app  # nopycln: import
from url_checker.create_apps import flask_app as app

# Finally, register all blueprints - after celery_app is fully created to avoid circular import like this
from url_checker.main import main  # noqa: E402

# Register Celery as a Flask extension here in the main module
# It is now done i nthe Flask app factory
# app.extensions["celery"] = celery_app


app.register_blueprint(main)
app.register_blueprint(admin)

# def main():
#    """For the demo, we simply (and log) printout the Hello World message."""
#    print("Hello World !")
#    logging.info("Print out done!")

if __name__ == "__main__":
    # main()
    app.run(debug=True)

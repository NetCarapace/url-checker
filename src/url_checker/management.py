"""
A script defining different CLI command to manage the Flask application and its content.
By design, these are various helper direct CLI commands that wrap snippets that may be run under the Flask shell:
Quick & dirty approach:
sudo -u urlchecker bash -c "source /etc/url-checker/.env && flask shell"

With Docker:
# In Dockerfile
COPY management.py /app/
RUN chmod +x /app/management.py

# In docker-compose
management:
  image: your-app
  command: python management.py db-status
  depends_on:
    - db

Please note that by design, this facility is prone to raise alerts in Security Scanners, yet we configure it safe as it
is only called by an admin from local CLI, by intention. To make it cleaner, we may move the script to Ansible part, but
the Developers would lose the ability to troubleshoot and clean up things in Dev environment; also, we like to version
this script alongside the rest of the code of this Web Application.
"""

import click
import pika
from pika.exceptions import AMQPConnectionError

from url_checker.create_apps import create_flask_app
from url_checker.database import sql_db_conn

app = create_flask_app()


def get_rabbitmq_channel():
    """Get RabbitMQ connection"""
    credentials = pika.PlainCredentials(
        app.config.get("RABBITMQ_USER", "guest"),
        app.config.get("RABBITMQ_PASSWORD", "guest"),
    )
    parameters = pika.ConnectionParameters(
        host=app.config.get("RABBITMQ_HOST", "localhost"),
        port=app.config.get("RABBITMQ_PORT", 5672),
        credentials=credentials,
    )
    connection = pika.BlockingConnection(parameters)
    return connection.channel()


@app.cli.command("db-purge")
def db_purge():
    """
    Purge ALL tables and Alembic history
    Run me with:
    uv run python management.py db-purge
    """
    if input("⚠️ PURGE ALL DATA? (type 'YES'): ") != "YES":
        return

    from sqlalchemy import text

    with app.app_context():
        print("Dropping all tables...")
        sql_db_conn.drop_all()
        sql_db_conn.session.commit()

        print("Dropping alembic_version table...")
        sql_db_conn.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
        sql_db_conn.session.commit()

        print("✅ Database purged!")


@app.cli.command("db-status")
def db_status():
    """Show database tables and row counts"""
    from sqlalchemy import inspect, text

    from url_checker.database import sql_db_conn as db

    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print("🗄️ Database Status\n")
        print(f"Tables found: {len(tables)}")
        print("-" * 40)

        for table in tables:
            # Count rows
            result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"{table:20s}: {result:>5} rows")

        # Check Alembic version
        if "alembic_version" in tables:
            version = db.session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            print(f"\nMigration version: {version}")
        else:
            print("\n⚠️  No alembic_version table")


# @app.cli.command("db-seed")
# def db_seed():
#    """Seed database with test data"""
#    with app.app_context():
#        ADD DATA HERE or read fixture
#        print("✅ Database seeded!")


# Broker and cacher
@app.cli.command("queues-clear")
def queues_clear():
    """⚠️ Clear ALL RabbitMQ queues (loses all tasks!)"""
    if input("⚠️ CLEAR ALL QUEUES? (type 'YES'): ") != "YES":
        return

    try:
        channel = get_rabbitmq_channel()
        channel.queue_purge(queue="")  # Purges default exchange
        # Or purge specific queues:
        # channel.queue_purge(queue="celery")
        channel.close()
        print("✅ All queues cleared!")
    except AMQPConnectionError:
        print("❌ RabbitMQ not available")


@app.cli.command("queues-status")
def queues_status():
    """Show queue stats"""
    try:
        import requests

        # RabbitMQ Management API (enable in RabbitMQ config)
        resp = requests.get(
            "http://localhost:15672/api/queues", auth=("guest", "guest")
        ).json()

        print("RabbitMQ Queues:")
        for q in resp:
            print(
                f"  {q['name']}: {q['messages_ready']} ready, "
                f"{q['messages_unacknowledged']} unacked"
            )
    except Exception:
        print("ℹ️  Run `docker run -p 15672:15672 rabbitmq:3-management` for API")


# Celery
@app.cli.command("tasks-retry-failed")
def tasks_retry_failed():
    """Retry failed Celery tasks"""
    if input("Retry ALL failed tasks? (type 'YES'): ") != "YES":
        return

    from celery import current_app

    with current_app.app_context():
        failed = current_app.control.inspect().failed()
        for _worker, tasks in failed.items():
            for task in tasks:
                current_app.control.retry_task(task["id"])
        print("✅ Retried failed tasks!")


# Health
@app.cli.command("health-check")
def health_check():
    """Run full health checks"""
    checks = [
        ("Database", lambda: sql_db_conn.engine.execute("SELECT 1").scalar()),
        (
            "RabbitMQ",
            lambda: get_rabbitmq_channel().queue_declare(queue="", passive=True),
        ),
    ]

    for name, check in checks:
        try:
            check()
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {e}")


@app.cli.command("logs-tail")
@click.option("--lines", default=100)
def logs_tail(lines):
    """Tail recent logs"""
    import subprocess

    subprocess.run(["tail", f"-n{lines}", "logs/app.log"])


# User management for later
# @app.cli.command("user-create")
# @click.argument("email")
# @click.argument("password")
# def user_create(email, password):
#    """Create admin user"""
#    with app.app_context():
#        from url_checker.models import User
#        user = User(email=email, is_admin=True)
#        user.set_password(password)
#        db.session.add(user)
#        db.session.commit()
#        print(f"✅ Created user {email}")
#

if __name__ == "__main__":
    app.cli()

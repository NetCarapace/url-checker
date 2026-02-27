#!/bin/bash
set -e

rm -rf /tmp/test-wheels
mkdir /tmp/test-wheels

packages=(
    "alembic==1.17.2"
    "amqp==5.3.1"
    "annotated-types==0.7.0"
    "billiard==4.2.4"
    "blinker==1.9.0"
    "celery==5.6.2"
    "certifi==2026.1.4"
    "charset-normalizer==3.4.4"
    "click==8.3.1"
    "click-didyoumean==0.3.1"
    "click-plugins==1.1.1.2"
    "click-repl==0.3.0"
    "commentjson==0.9.0"
    "flask==3.1.2"
    "flask-migrate==4.1.0"
    "flask-sqlalchemy==3.1.1"
    "flower==2.0.1"
    "greenlet==3.3.0"
    "humanize==4.15.0"
    "idna==3.11"
    "itsdangerous==2.2.0"
    "jinja2==3.1.6"
    "kombu==5.6.2"
    "lark-parser==0.7.8"
    "mako==1.3.10"
    "markupsafe==3.0.3"
    "packaging==25.0"
    "prometheus-client==0.23.1"
    "prompt-toolkit==3.0.52"
    "pydantic==2.12.5"
    "pydantic-core==2.41.5"
    "pydantic-settings==2.12.0"
    "pymysql==1.1.2"
    "python-dateutil==2.9.0.post0"
    "python-dotenv==1.2.1"
    "pytz==2025.2"
    "requests==2.32.5"
    "six==1.17.0"
    "sqlalchemy==2.0.45"
    "tornado==6.5.4"
    "typing-extensions==4.15.0"
    "typing-inspection==0.4.2"
    "tzdata==2025.3"
    "tzlocal==5.3.1"
    "urllib3==2.6.3"
    "vine==5.1.0"
    "wcwidth==0.2.14"
    "werkzeug==3.1.5"
)

echo "Testing each package individually..."
echo ""

for pkg in "${packages[@]}"; do
    pkg_name=$(echo "$pkg" | cut -d'=' -f1)

    echo -n "Downloading $pkg_name ... "

    before=$(du -sb /tmp/test-wheels 2>/dev/null | cut -f1)
    [ -z "$before" ] && before=0

    pip download "$pkg" --dest /tmp/test-wheels/ --prefer-binary >/dev/null 2>&1

    after=$(du -sb /tmp/test-wheels | cut -f1)
    diff=$((after - before))
    diff_mb=$((diff / 1024 / 1024))

    if [ $diff_mb -gt 50 ]; then
        echo "⚠️  ${diff_mb}MB (LARGE!)"
    else
        echo "${diff_mb}MB"
    fi
done

echo ""
echo "=== Total size ==="
du -sh /tmp/test-wheels/
echo ""
echo "=== Top 10 largest files ==="
ls -lhS /tmp/test-wheels/ | head -11

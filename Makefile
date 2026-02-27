# /!\ /!\ /!\ /!\ /!\ /!\ /!\ DISCLAIMER /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\/!\ /!\ /!\/!\
#
# This Makefile is only meant to be used for DEVELOPMENT purpose as we are
# changing the user id that will run in the container.
#
# PLEASE DO NOT USE IT FOR YOUR PRODUCTION...
#
# /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\ /!\/!\ /!\ /!\/!\
########################################################################################
# How-to use
########################################################################################
# Run the make with as follow:
#
# ```bash
# make ${make_target} \
#      version_repo="X.Y.Z" \
#      tag_message = "the message your may want to associate with the Git tag" \
# ```

BOLD := \033[1m
RESET := \033[0m
GREEN := \033[1;32m
RED := \033[31m
BOLD_GREEN := \033[1;32m

########################################################################################
# PREAMBLE - OS AND DEPENDENCY CHECKS
########################################################################################
# Detect OS
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    $(info ✅ Running on Linux)
    OS := Linux
	# Detect package manager
    ifneq (,$(shell command -v apt 2> /dev/null))
        PKG_MANAGER := apt
    else ifneq (,$(shell command -v dnf 2> /dev/null))
        PKG_MANAGER := dnf
    else ifneq (,$(shell command -v yum 2> /dev/null))
        PKG_MANAGER := yum
    else ifneq (,$(shell command -v zypper 2> /dev/null))
        PKG_MANAGER := zypper
    else ifneq (,$(shell command -v pacman 2> /dev/null))
        PKG_MANAGER := pacman
    else
        $(error ❌ Unable to detect package manager (apt, dnf, yum, zypper, or pacman))
    endif
    $(info ✅ Package manager detected: $(PKG_MANAGER))
else ifeq ($(UNAME_S),Darwin)
    $(info ✅ Running on macOS)
    OS := macOS
else
    $(error ❌ Unsupported OS: $(UNAME_S). Only Linux and macOS are supported.)
endif
UNAME_S :=

# Check for bash

ifeq (,$(shell command -v bash 2> /dev/null))
    $(error ❌ bash not found. Please install bash.)
else
    $(info ✅ bash found: $(shell command -v bash))
endif

# Check for uv
ifeq (,$(shell command -v uv 2> /dev/null))
    $(error ❌ uv not found. Please install uv, ideally with your package manager, or from https://github.com/astral-sh/uv)
else
    UV_VERSION := $(shell uv --version 2>/dev/null)
    $(info ✅ uv found: $(UV_VERSION))
endif
UV_VERSION :=


########################################################################################
# VARIABLES
########################################################################################

# Use Bash and its facilities
SHELL := /bin/bash

# Extract Python version from pyproject.toml and create .python-version
# This file is needed by uv and pip for building the bundle
# We also include it into the .tar.gz bundle.
$(shell \
  if [ ! -f .python-version ]; then \
    python3 -c "import tomllib; \
      data = tomllib.load(open('pyproject.toml', 'rb')); \
      req = data['project']['requires-python']; \
      version = req.replace('>=', '').split('.')[0:2]; \
      print('.'.join(version))" > .python-version 2>/dev/null; \ # || echo "3.13" > .python-version; \
  fi \
)

# Setup environments
# We include files if they exists, or create them from templates for init_repo recipe
ifneq ($(wildcard ./.envinit),)
include .envinit
export $(shell sed 's/=.*//' .envinit)
endif

# Check for the presence of envfiles
envfiles := .envbuild .envtest .envdev .env
env_file_non_present := 0

define check_envfile
ifeq ($$(wildcard ./$(1)),)
$$(info $(1) file was created from template.)
$$(shell cp $(1).template $(1))
$$(eval env_file_non_present := 1)
endif
endef

$(foreach envfile,$(envfiles),$(eval $(call check_envfile,$(envfile))))

ifeq ($(env_file_non_present),1)
$(shell echo -e "$(RED)$(BOLD)At least one envfile was recreated from template, please modify varenvs: run configure_repo_dev or manually.$(RESET)" >&2)
$(error ❌ Please correct and run again. ❌)
endif
env_file_non_present :=
envfile :=

# Include their content on next runs
-include $(envfiles)
$(foreach file,$(envfiles),$(eval export $(shell sed 's/=.*//' $(file))))

# Setup config file
ifeq ($(wildcard ./urlchecker_config.json),)
$(shell cp urlchecker_config.json.template urlchecker_config.json)
$(error urlchecker_config.json created from template, please modify it manually with your own values.)
endif

# Build intermediary variables
# We currently use the debian convention at some level
# Even if our package is not really a debian package yet
PACKAGE_VERSION = $(shell cat VERSION)
PACKAGE_PYTHON = $(shell cat .python-version)
PACKAGE_SUFFIX = deployment-bundle.tar.gz
PACKAGE_FULLNAME = ${URLCHECKER_PACKAGE_NAME}_v${PACKAGE_VERSION}_Python${PACKAGE_PYTHON}-${PACKAGE_SUFFIX}


# Houskeeping forcing variables
# We reserve normally automation for CI/CD - Experimental in this repo
automatic = "N"
#
# this one is to bump version, different from PACKAGE_VERSION which only reads Version state
version_repo = "0.0.0"
#
tag_message = ""
venv_dir = ".venv"
venv_command = ". $(venv_dir)/bin/activate"
#
new_package = ""

########################################################################################
# RULES
########################################################################################

.SILENT:
.PHONY: configure_repo_dev \
		clean \
		testclean \
		distclean \
		coverageclean \
		run_dev_infra \
		migrate_db \
		run \
		nuke

# Init
########################################################################################
configure_repo_dev: install-dev
# TODO Help the User to create the .envdev and .env files
	uv sync --locked; \
	echo "${venv_command}"; \
	uv run pip3 list; \
	go_to_install="N"; \
	if [ ${automatic} = "N" ]; then \
		echo "Reply Y if and only if the pip3 list output above is consistent and does not display system packages !"; \
		echo "Ctrl+C to escape ..."; \
		read -p "Do you want to install other specific dependencies from specific requirement files with pip ? (Y/N) " go_to_install; \
	if [ $$go_to_install = "Y" ] || [ $$go_to_install = "y" ]; then \
		uv run pip3 install -r requirements-dev.txt -e .; \
	else
		echo "Tweak requirements-dev.txt skipped"; \
	fi \
	fi

	uv run pre-commit install; \
	uv run pre-commit autoupdate; \
	echo "Initial pre-commit run"; \
	uv run pre-commit run --all-files; \
	echo "Virtual environment created, local repo configured with pre-commit hooks."; \

	cd /tmp;# \
	# git clone TODO ADD Github stuff

# Development lifecycle #
########################################################################################
# Dependencies
# -dev suffixes means we specifically manage dependencies present only in Dev Environment
install_deps:
	uv venv --seed
	uv sync --locked


install-dev:
	uv venv --seed
	uv sync --dev --locked
	uv pip install pip

add_newdep:
	uv add $(new_package)

add_newdep-dev:
	uv add --dev $(new_package)

update_deps:
	uv lock --upgrade
	uv sync --locked
########################################################################################

# Database Management
# If your change led to change in database model, you need migration file to update your database state prior to running
new_migration: run_dev_infra
	@echo "💣 DO NOT RUN IN PRODUCTION !!! Press Enter to continue or Ctrl+C to exit";
	read wait_for_me; \
	echo "Waiting 5 seconds for database available..."
	sleep 5
	uv run flask db upgrade --directory src/$(PACKAGENAME)/migrations
	echo "Database created if not existed, previous migrations applied"
	uv run flask db migrate --directory src/$(PACKAGENAME)/migrations
	echo "New migration created if new model found"
	uv run flask db upgrade --directory src/$(PACKAGENAME)/migrations
	sleep 1
	echo "New migrations applied"
	# Stop test infra
	cd docker && docker compose down
	echo "To stop adminer, provide password for sudo ..."
	sudo systemctl stop apache2.service

migrate_db: run_dev_infra
	echo "Waiting 5 seconds for database available..."
	sleep 5
	# In prod, we should early escape if user and database does not exist because we cannot use root password !
	uv run flask db upgrade --directory src/$(PACKAGENAME)/migrations
	sleep 1
	echo "Database created if not existed, migrations applied"
	# Stop test infra
	cd docker && docker compose down
	echo "To stop adminer, provide password for sudo ..."
	sudo systemctl stop apache2.service

# At the very start of the project, ONLY BY project owner and maintainer
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
init_migrations: nuke_db
	rm -rf src/$(PACKAGENAME)/migrations
	echo "Migrations folder deleted"
	cd docker && docker compose up -d
	echo "Waiting 10 seconds for data init ..."
	sleep 10
	uv run flask db init --multidb --directory src/$(PACKAGENAME)/migrations
	echo "Dummy Database Initialisation done"
	cp contrib/env.py.custom src/$(PACKAGENAME)/migrations/env.py
	echo "env.py patched"
	uv run flask db migrate -m "Initial migration" --directory src/$(PACKAGENAME)/migrations
	echo "Initial migration created"
	uv run flask db upgrade --directory src/$(PACKAGENAME)/migrations
	echo "First upgrade"
	# Stop test infra
	cd docker && docker compose down
	# Nuke db
	sudo rm -rf docker/mariadb/data
	sudo rm -rf docker/mariadb/logs
	echo "Dummy database deleted"
	echo "Actual schema and database will be created on first run of the web app."
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
########################################################################################

# Run Application
run: run_dev_infra
	echo "Waiting 5 seconds for database available..."
	sleep 5
	uv run flask db upgrade --directory src/$(PACKAGENAME)/migrations
	sleep 1
	./run_devloc_app.sh
	# Stop test infra (not functionnal yet, might need utilities scripts)
	cd docker && docker compose down
	echo "To stop adminer, provide password for sudo ..."
	sudo systemctl stop apache2.service
########################################################################################

# Build 🌍 , Publish  🌬️ and Release 🔥
build: update_deps clean
	# Export uv.lock to requirements-build.txt for downloading
	echo "Create requirements-build.txt";
	uv export \
	  --format requirements.txt \
	  --no-hashes \
	  --frozen \
	  --no-editable \
	  --no-emit-project > requirements-build.txt;
	# Export all wheel
	echo "Download wheel";
	mkdir -p offline-wheels;
	# Download ONLY the locked dependencies for this project
	uv run pip download \
	  -r requirements-build.txt \
	  --dest offline-wheels/ \
      --prefer-binary
	# Add build package tools
	# python3 -m pip download setuptools wheel pip --dest offline-wheels/
	python3 -m pip download \
	  setuptools \
	  --dest offline-wheels \
	  --prefer-binary
	# Bundle everything
	echo "Bundle it";
	tar czf ${PACKAGE_FULLNAME} \
	  --transform='s|^src/$(PACKAGENAME)|$(PACKAGENAME)|' \
      src/$(PACKAGENAME) \
	  doc \
	  docker \
	  Makefile \
	  .env.template \
	  urlchecker_config.json.template \
	  .python-version \
      pyproject.toml \
	  requirements-build.txt \
      uv.lock \
	  CHANGELOG.md \
	  CONTRIBUTORS.md \
	  UPGRADING_NOTES.md \
	  README.md \
	  RELEASE_NOTES.md \
	  VERSION \
	  offline-wheels;

publish:
    # Configuration
	read -s -p "GitLab Token: " GITLAB_TOKEN; \
	echo "Publishing to GitLab Package Registry..."; \
	echo "--upload-file ${PACKAGE_FULLNAME}"; \
	echo "${URLCHECKER_GITLAB_CI_API_V4_URL}/projects/${URLCHECKER_GITLAB_PROJECT_ID}/packages/generic/${PACKAGE_DEBIANNAME}/${PACKAGE_VERSION}/${PACKAGE_FULLNAME}"; \
	curl --header "PRIVATE-TOKEN: $$GITLAB_TOKEN" \
	  --upload-file ${PACKAGE_FULLNAME} \
	  "${URLCHECKER_GITLAB_CI_API_V4_URL}/projects/${URLCHECKER_GITLAB_PROJECT_ID}/packages/generic/${PACKAGE_DEBIANNAME}/${PACKAGE_VERSION}/${PACKAGE_FULLNAME}"; \
	echo "✅ Published: ${PACKAGE_DEBIANNAME} version is ${PACKAGE_VERSION}"

release: build publish
	@echo "✅ Release complete"
########################################################################################

# Various Helpers
run_dev_infra:
	cd docker && docker compose up -d
	echo "To run adminer, provide password for sudo ..."
	sudo systemctl start apache2.service

run_dev_worker:
	uv run celery -A celery_worker.celery worker --loglevel=info

stop_dev_infra:
	cd docker && docker compose down
	echo "To stop adminer, provide password for sudo ..."
	sudo systemctl stop apache2.service
########################################################################################

# Test
########################################################################################
# Unit tests
test_units: run_dev_infra
	uv run python tests/run_tests.py
	# Stop test infra
	cd docker && docker compose down
	echo "To stop adminer, provide password for sudo ..."
	sudo systemctl stop apache2.service
########################################################################################

# Integration tests
test_one_post_testinstance:
	echo "Facility for testing a specific (faulty ?) endpoint on test..."
	read -s -p "API-TOKEN Token: " API_TOKEN; \
	curl -X POST \
		-H "Authorization: Bearer $$API_TOKEN" \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running.json \
		${URLCHECKER_TESTURL}/main/urls

test_one_post_while_running:
# Add a dep on "run" and possibly check in run recipe that the webapp is not already up
	echo "Facility for testing a specific (faulty ?) endpoint ..."
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running_valid_reachable_malicious_1.json \
		http://127.0.0.1:5000/main/urls

test_all_fail_post_while_running_full:
# Add a dep on "run" and possibly check in run recipe that the webapp is not already up
	fname=test_while_running_fail_invalid1; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_fail_invalid2; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_fail_invalid3; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid1; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid2; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid3; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid4; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid5; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid6; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid7; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid8; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid9; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid10; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls
	fname=test_while_running_valid11; \
	echo tests/$$fname.json; \
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/$$fname.json \
		http://127.0.0.1:5000/main/urls



test_while_running:
# Add a dep on "run" and possibly check in run recipe that the webapp is not already up
	# With token
	echo "Should be accepted ..."
	curl -X POST \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running.json \
		http://127.0.0.1:5000/main/urls
	echo ""
	# Bad token
	echo "Should be rejected ..."
	curl -X POST \
		-H "Authorization: Bearer your-api-bad-token" \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running.json \
		http://127.0.0.1:5000/main/urls
	echo ""
	echo "Waiting for completion of submitted job"
	sleep 1
	echo ""
	# No token
	echo "Should be rejected ..."
	curl -X POST \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running.json \
		http://127.0.0.1:5000/main/urls
	# Header Typo
	echo ""
	echo "Should be rejected ..."
	curl -X POST \
	    -H "Authorisation: Bearer your-api-bad-token" \
		-H "Content-Type: application/json" \
		-d @tests/test_while_running.json \
		http://127.0.0.1:5000/main/urls
	echo ""
	echo "Check a get ..."
	curl \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/urls/all
	echo ""
	echo "Check another get ..."
	curl \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/jobs/all
	echo ""
	echo "Check another get with bad token..."
	curl \
		-H "Authorization: Bearer your-api-bad-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/jobs/all
	echo ""
	echo "Check health ..."
	curl \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/health
	echo ""
	echo "Check final get to have complete overview before deleting all data..."
	curl \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/results/all
	echo ""
	echo "Delete all jobs ..."
	curl -X DELETE \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/jobs/all
	echo ""
	echo "Delete all Results -> 0 deleted because all Jobs already gone ..."
	curl -X DELETE \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/results/all
	echo ""
	echo "Delete all Urls ..."
	curl -X DELETE \
		-H "Authorization: Bearer your-api-token" \
		-H "Content-Type: application/json" \
		http://127.0.0.1:5000/main/urls/all
########################################################################################

################
# Housekeeping #
################
format_and_lint:
	uv run pre-commit run --all-files --show-diff-on-failure --verbose;

bump_version: VERSION
ifeq (${version_repo},"0.0.0")
	@echo "❌ Provide version_repo=X.Y.Z on CLI"
	@echo "Usage: make bump_version version_repo=1.2.3"
else
	@echo "✅ Ensure clean working directory first"
	@if ! git diff-index --quiet HEAD --; then \
		echo "❌ Working directory is dirty. Commit or stash changes first."; \
		exit 1; \
	fi

	@echo "🔄 Pulling latest changes..."
	git pull

	@echo "📝 Bumping repo to version ${version_repo}"
	echo ${version_repo} > VERSION
	sed -i "s/.*__version__.*/__version__ = \"${version_repo}\"/" "src/$(PACKAGENAME)/__init__.py"
	sed -i "s/.*version =.*/version = \"${version_repo}\"/" "pyproject.toml"

	@echo "🔒 Updating uv.lock..."
	uv lock

	@echo "📦 Staging changes..."
	git add VERSION
	git add "src/$(PACKAGENAME)/__init__.py"
	git add "pyproject.toml"
	git add uv.lock

	@echo "💾 Committing changes..."
	git commit -m "BUMP to version ${version_repo}"

	@echo "🏷️  Creating tag ${version_repo}..."
	git tag ${version_repo} -m "${tag_message}"

	@echo "🚀 Pushing to remote..."
	git push
	git push --tags

	@echo "✅ Version bumped to ${version_repo}"
endif

clean:
	-find . -name __pycache__ -print0 | xargs -0 rm -rf
	-find . -name "*.pyc" -print0 | xargs -0 rm -rf
	-find . -name "*.egg-info" -print0 | xargs -0 rm -rf

coverageclean:
	-rm src/urlchecker/.coverage
	-rm src/urlchecker/.coverage.*
	-rm src/urlchecker/coverage.xml
	-rm -rf src/urlchecker/htmlcov

distclean:
	-rm -rf ./dist
	-rm -rf ./build
	-rm -rf ./venv

nuke: clean distclean testclean

testclean: coverageclean clean
	-rm -rf .tox

nuke_db: stop_dev_infra
	@echo "💣 DO NOT RUN IN PRODUCTION !!! Press Enter to continue or Ctrl+C to exit"
	read wait_for_me; \
	sudo rm -rf docker-tmp # mariadb/data and mariadb/logs
	echo "Database logs and data folders deleted"
	echo ""

################
# Makefile Doc #
################

help :
	echo ""
	echo -e "${BLUE}${BOLD}### I am your quick and dirty Help file :) ###${RESET}"
	echo ""
	echo -e "${BOLD}# Run make with targets like:${RESET}"
	echo "make target someparameter=\"somevalue\""
	echo ""
	echo -e "${GREEN}# Available combinations arguments/targets/description:${RESET}"
	echo ""
	echo -e "${BOLD}🛠️  Initialize local dev environment:${RESET}"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "configure_repo_dev" "/" "Configure local Python3 venv + pre-commit hooks"
	echo ""
	echo -e "${BOLD}📦 Development lifecycle:${RESET}"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "new_migration" "/"  "Create new migration script"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "migrate_db" "/"  "Apply migrations sequentially"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "run" "/"  "Run Dev Flask server (local venv) + Dev Infrastructure (docker-compose)"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "stop_dev_infra" "/"  "Stop Dev Infrastructure  manually when things gone stuck (docker-compose)"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "format_and_lint" "/"  "Format + lint (pre-commit style)"
	@printf "  %-20s %s %-20s %s %s\n" "[new_package="package-name"]" "/" "add_newdep-dev" "/"  "Just add one new dep in dev mode"
	echo ""
	echo -e "${BOLD}🔥 Build, 🌬️  Publish and 🚀 Release:${RESET}"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "build" "/" "Build locally a .tar.gz for distribution"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "publish" "/" "Publish the build to a Registry (tested with Gitlab on-prem instances)"
	echo ""
	echo -e "${BOLD}🧪 Tests:${RESET}"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "test_units" "/"  "Run unit test suite"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "test_one_post_testinstance" "/"  "Run one real URL on the remote test infra"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "test_one_post_while_running" "/"  "Run one real URL on the local dev infra (dev instance must be running in separate terminals)"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "test_all_fail_post_while_running_full" "/"  "Run a list of predefined failing urls and API requests on the local dev infra  (dev instance must be running in separate terminals)"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "test_while_running" "/"  "Run a list of predefined urls and API requests on the local dev infra  (dev instance must be running in separate terminals)"
	echo ""
	echo -e "${BOLD}🧹 Housekeeping:${RESET}"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "format_and_lint" "/" "Run the formatter and linter our of pre-commit hooks"
	@printf "  %-20s %s %-20s %s %s\n" "[version_repo=X.Y.Z]" "/" "bump_version" "/" "Bump version + tag (use version_repo=X.Y.Z)"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "clean" "/" "Clean Python artifacts"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "coverageclean" "/" "Clean Coverage test artifacts"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "distclean" "/" "Clean Build and Dist artifacts"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "venvclean" "/" "Clean .venv artifacts"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "nuke" "/" "Chain the cleaning steps above"
	@printf "  %-20s %s %-20s %s %s\n" "[none]" "/" "nuke_db" "/" "Trash the local instance, including database"
	echo ""
	echo -e "${BOLD}💡 Examples:${RESET}"
	echo "  make configure_repo_dev"
	echo "  make run"
	echo "  make bump_version version_repo=1.2.3 tag_message=\"Release v1.2.3\""
	echo ""
	echo -e "${BOLD}📝 Default arguments that can be superseded on CLI:${RESET}"
	echo "- automatic=\"N\""
	echo "- version_repo=\"0.0.0\""
	echo "-	tag_message=\"\""
	echo "- new_package=\"\""
	echo ""
	echo "To provide API RO Tokens and Remote Test config, configure the .env and manage it with care or, better use the key_manager tool to integrate to keychain"
	echo "For publishing to your Registry, configure the .envdev varenvs"
	@printf "\033[0;32m%s\033[0m\n" "Run 'make help' anytime for this reference"

SHELL := pwsh

.PHONY: help setup pre-commit lint lint-server lint-web typecheck test test-api test-web ci-api ci-web

help:
	@echo "Common tasks:"
	@echo "  make setup           # install dev tools (pre-commit hooks)"
	@echo "  make pre-commit      # run pre-commit across repo"
	@echo "  make lint            # lint server and web"
	@echo "  make typecheck       # mypy (server) + tsc (web)"
	@echo "  make test            # run focused API tests and web UI tests"

setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r server/requirements.txt
	pip install -r requirements-dev.txt
	if (Get-Command pre-commit -ErrorAction SilentlyContinue) { pre-commit install } else { python -m pip install pre-commit; pre-commit install }

pre-commit:
	pre-commit run --all-files

lint: lint-server lint-web

lint-server:
	ruff check .
	black --check .

lint-web:
	cd web; if (!(Test-Path node_modules)) { npm ci }; npm run lint

typecheck:
	mypy server app || echo "mypy warnings allowed for now"
	cd web; npm run typecheck

test: test-api test-web

test-api:
	$env:DB_URL="sqlite:///:memory:"; pytest tests/server tests/infrastructure tests/scripts -q

test-web:
	cd web; npm run test -s

ci-api: lint-server typecheck test-api

ci-web: lint-web typecheck test-web

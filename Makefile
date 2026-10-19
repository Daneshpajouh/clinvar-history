PY ?= .venv/bin/python
PG_DSN ?= postgresql://clinvar_history:clinvar_history@127.0.0.1:55432/clinvar_history

.PHONY: install lint test test-pg check docs image

install:
	python3 -m venv .venv && .venv/bin/pip install -e ".[postgres,dev,docs]"

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests
	$(PY) -m mypy
	.venv/bin/sqlfluff lint migrations sql

test:
	$(PY) -m pytest -q

test-pg:
	docker compose up -d db
	CLINVAR_HISTORY_PG_DSN=$(PG_DSN) $(PY) -m pytest -q --cov=clinvar_history

check: lint test

docs:
	.venv/bin/mkdocs build --strict

image:
	docker build -t clinvar-history:1.0.2 .

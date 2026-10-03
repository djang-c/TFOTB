# One entry point. Toolchain pinned in mise.toml; Python deps in requirements.lock;
# JS deps in frontend/pnpm-lock.yaml. Run `make setup` on a fresh clone.
SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
MISE := mise exec --
WEB := cd frontend && $(MISE) pnpm

.PHONY: setup dev api web test lint typegen e2e lock

setup:
	mise install
	test -d $(VENV) || $(MISE) python -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.lock
	$(PY) -m pip install -q --no-deps -e .
	$(WEB) install --frozen-lockfile
	test -f .env || cp env.example .env

dev:
	$(MAKE) -j2 api web

api:
	$(PY) -m uvicorn atlas.api.app:app --reload --port $${PORT:-8000}

web:
	$(WEB) dev

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
	$(WEB) lint
	$(WEB) typecheck

typegen:
	mkdir -p data/build
	$(PY) -c "import json; from atlas.api import create_app; print(json.dumps(create_app().openapi()))" > data/build/openapi.json
	$(WEB) typegen

e2e:
	$(WEB) e2e

# Re-freeze Python deps after changing pyproject.toml.
lock:
	$(PY) -m pip freeze --exclude-editable | grep -vi '^tfotb' > requirements.lock

# One entry point. Toolchain pinned in mise.toml; Python deps in requirements.lock;
# JS deps in frontend/package-lock.json (npm). Run `make setup` on a fresh clone.
SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
MISE := mise exec --
WEB := cd frontend && $(MISE) npm

.PHONY: setup dev api web test lint e2e build lock

setup:
	mise install
	test -d $(VENV) || $(MISE) python -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.lock
	$(PY) -m pip install -q --no-deps -e .
	$(WEB) ci
	test -f .env || cp env.example .env

dev:
	$(MAKE) -j2 api web

api:
	$(PY) -m uvicorn atlas.api.app:app --reload --port $${PORT:-8000}

web:
	$(WEB) run dev

test:
	$(PY) -m pytest -q
	$(WEB) test

lint:
	$(PY) -m ruff check .
	$(WEB) run lint
	$(WEB) run typecheck

build:
	$(WEB) run build

# Drives the real frontend and API in headless Chrome. Start `make dev` first. See frontend/README.md.
e2e:
	$(WEB) run e2e

# Re-freeze Python deps after changing pyproject.toml.
lock:
	$(PY) -m pip freeze --exclude-editable | grep -vi '^tfotb' > requirements.lock

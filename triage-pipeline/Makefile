.PHONY: help install up down restart logs migrate test eval lint format clean sample-run

help:
	@echo "AI Triage Pipeline — common targets"
	@echo ""
	@echo "  install      Install Python dependencies in a local venv"
	@echo "  up           Start the full stack (postgres, redis, app, worker)"
	@echo "  up-obs       Start with observability profile (prometheus, grafana)"
	@echo "  down         Stop and remove containers"
	@echo "  restart      Restart app + worker"
	@echo "  logs         Tail app + worker logs"
	@echo "  migrate      Apply Alembic migrations"
	@echo "  test         Run the unit + graph test suites"
	@echo "  test-all     Run all tests including integration"
	@echo "  lint         Ruff + mypy"
	@echo "  format       Ruff format"
	@echo "  sample-run   Run the 5 sample inputs from the brief and emit JSON"
	@echo "  clean        Remove caches"

install:
	python -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -e ".[dev]"

up:
	docker compose up -d --build

up-obs:
	docker compose --profile observability up -d --build

down:
	docker compose down

restart:
	docker compose restart app worker

logs:
	docker compose logs -f app worker

migrate:
	docker compose run --rm migrate

test:
	pytest -q tests/unit tests/graph

test-all:
	pytest -q

lint:
	ruff check src tests && mypy src

format:
	ruff format src tests

sample-run:
	python scripts/run_samples.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

# OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
.PHONY: help up down logs test lint format migrate revision seed-hooks fresh

help:
	@echo "OmniScale Enterprise Pro — common commands"
	@echo "  make up          Start the full stack (docker compose)"
	@echo "  make down        Stop the stack"
	@echo "  make logs        Tail all container logs"
	@echo "  make test        Run the pytest suite with coverage"
	@echo "  make lint        Run ruff over backend + tests"
	@echo "  make format      Auto-fix lint issues + format"
	@echo "  make migrate     Apply pending Alembic migrations"
	@echo "  make revision m='message'   Create a new Alembic revision"
	@echo "  make seed-hooks  Install pre-commit hooks locally"
	@echo "  make fresh       Rebuild everything from a clean slate"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	pytest --cov=backend --cov-report=term-missing

lint:
	ruff check backend tests

format:
	ruff check --fix backend tests
	ruff format backend tests

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

seed-hooks:
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type pre-push

fresh:
	docker compose down -v
	docker compose up --build

.PHONY: help up down test backend worker frontend do-it-all do_it_all check check-stack

help:
	@echo "Available commands:"
	@echo "  make do-it-all   # Start full stack (non-coder quickstart)"
	@echo "  make check       # Health check backend/frontend/auth/jobs"
	@echo "  make up          # docker compose up --build"
	@echo "  make down        # docker compose down -v"
	@echo "  make backend     # run FastAPI locally"
	@echo "  make worker      # run Celery worker locally"
	@echo "  make frontend    # run Next.js locally"
	@echo "  make test        # run backend tests"

up:
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down -v

backend:
	cd backend && uvicorn app.main:app --reload

worker:
	cd backend && celery -A app.workers.celery_app.celery_app worker -Q video --loglevel=INFO

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

do-it-all:
	./scripts/do_it_all.sh

# Alias to handle underscore usage on different instructions.
do_it_all: do-it-all

check:
	./scripts/check_stack.sh

# Alias for discoverability.
check-stack: check

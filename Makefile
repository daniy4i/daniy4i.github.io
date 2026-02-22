.PHONY: up down test backend worker frontend
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

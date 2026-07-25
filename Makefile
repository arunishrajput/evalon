.PHONY: dev up down logs migrate seed test shell model-status model-unload worker-scale-2 backend-install frontend-install

# --- Primary local dev workflow (CLAUDE.md) ---
# postgres + redis in docker; backend + frontend run natively with hot reload
dev:
	docker compose up -d postgres redis
	@echo "postgres + redis are up. Run backend and frontend natively:"
	@echo "  cd backend  && uvicorn app.main:app --reload"
	@echo "  cd frontend && npm run dev"

# --- Full Docker Compose stack ---
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m app.scripts.seed

test:
	docker compose exec backend pytest

shell:
	docker compose exec backend /bin/bash

model-status:
	curl -s http://localhost:8000/api/v1/admin/model/status | python3 -m json.tool

model-unload:
	curl -s -X POST http://localhost:8000/api/v1/admin/model/unload | python3 -m json.tool

worker-scale-2:
	docker compose up -d --scale worker=2

backend-install:
	cd backend && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt

frontend-install:
	cd frontend && npm install

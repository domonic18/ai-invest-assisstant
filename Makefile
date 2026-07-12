.PHONY: dev infra backend web lint test build setup sync

# Start infrastructure services
infra:
	docker compose -f docker-compose.infra.yml up -d

# Start backend development server
backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Start web development server
web:
	cd web && pnpm dev || npm run dev

# Sync Python dependencies
sync:
	cd backend && uv sync

# Run lint checks
lint:
	cd backend && uv run ruff check .
	cd web && pnpm lint || npm run lint

# Run tests
test:
	cd backend && uv run pytest -m unit
	cd web && pnpm test:unit -- --run || npm run test:unit -- --run

# Build Docker images
build:
	docker build -t web-api:latest -f docker/web/Dockerfile .
	docker build -t collector:latest -f docker/collector/Dockerfile .

# Local development setup
setup:
	bash scripts/setup-local.sh

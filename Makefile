.PHONY: up down migrate api scraper web

up:
	docker compose up -d db redis

down:
	docker compose down

migrate:
	cd api && go run ./cmd/migrate up

api:
	cd api && go run ./cmd/api

scraper:
	cd scraper && python -m scraper.worker

web:
	cd web && pnpm dev

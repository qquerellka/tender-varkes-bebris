.PHONY: up down restart logs ps build backend-logs frontend-logs semantic-up semantic-restart semantic-logs

up:
	docker compose up --build

down:
	docker compose down

restart:
	docker compose down
	docker compose up --build

logs:
	docker compose logs -f

ps:
	docker compose ps

build:
	docker compose build

backend-logs:
	docker compose logs -f backend

frontend-logs:
	docker compose logs -f frontend

semantic-up:
	docker compose up -d --build backend frontend

semantic-restart:
	docker compose up -d --force-recreate backend frontend

semantic-logs:
	docker compose logs -f backend frontend

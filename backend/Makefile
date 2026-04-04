.PHONY: install db-up db-down backend-up backend-logs migrate seed seed-synthetic seed-portal split-synthetic ml-prepare bootstrap run dev reset-db

install:
	pip install -e .

db-up:
	docker compose up -d

db-down:
	docker compose down

backend-up:
	docker compose up --build backend

backend-logs:
	docker compose logs -f backend

migrate:
	alembic upgrade head

seed:
	python -m app.bootstrap

seed-synthetic:
	python ../ML/tools/load_synthetic_to_backend.py

seed-portal:
	python -m app.import_portal_csv --ste-csv ../СТЕ_20260403.csv --contracts-csv ../Контракты_20260403.csv

split-synthetic:
	python ../ML/tools/build_ml_splits.py

ml-prepare: seed-synthetic split-synthetic

bootstrap: migrate seed

run:
	uvicorn app.main:app --reload

dev: db-up bootstrap run

reset-db:
	docker compose down -v
	docker compose up -d
	alembic upgrade head
	python -m app.bootstrap

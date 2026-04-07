.PHONY: install db-up db-down backend-up backend-logs migrate seed seed-portal build-orig-dataset split-orig train-ranker ml-prepare bootstrap run dev reset-db

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

seed-portal:
	python -m app.import_portal_csv --ste-csv ../ML/data/orig/СТЕ_20260403/СТЕ_20260403.csv --contracts-csv ../ML/data/orig/Контракты_20260403/Контракты_20260403.csv

build-orig-dataset:
	python ../ML/tools/build_portal_dataset.py

split-orig:
	python ../ML/tools/build_ml_splits.py --source-dir ../ML/data/orig/derived --output-dir ../ML/data/orig/derived/splits

train-ranker:
	python ../ML/tools/train_ranker.py --splits-dir ../ML/data/orig/derived/splits --artifacts-dir ../ML/models/catboost_ranker_v1

ml-prepare: build-orig-dataset split-orig train-ranker

bootstrap: migrate seed

run:
	uvicorn app.main:app --reload

dev: db-up bootstrap run

reset-db:
	docker compose down -v
	docker compose up -d
	alembic upgrade head
	python -m app.bootstrap

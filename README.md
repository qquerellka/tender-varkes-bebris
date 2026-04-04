# Tender Portal MVP

MVP-каталог СТЕ для сценариев закупки, поиска и анализа конкурентов.

В репозитории есть:
- `frontend` на `React + Vite + Ant Design + styled-components`
- `backend` на `FastAPI + PostgreSQL + SQLAlchemy + Alembic`
- demo-auth с готовыми пользователями
- роли `customer` и `supplier`
- `favorites`, `compare`, `cart`
- supplier dashboard
- rule-based personalization и опциональный ML reranking

## Структура

- [frontend/README.md](./frontend/README.md)
- [backend/README.md](./backend/README.md)
- [backend/ARCHITECTURE.md](./backend/ARCHITECTURE.md)
- [backend/TELEMETRY_SPEC.md](./backend/TELEMETRY_SPEC.md)
- [docker-compose.yml](./docker-compose.yml)
- [Makefile](./Makefile)

## Быстрый старт через Docker

Это основной и самый простой сценарий запуска.

```bash
cp .env.example .env
docker compose up --build
```

Или через `Makefile`:

```bash
cp .env.example .env
make up
```

После запуска:
- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- swagger: `http://localhost:8000/docs`
- healthcheck: `http://localhost:8000/health`

Что поднимется:
- `postgres`
- `backend`
- `frontend`

## Локальная разработка без Docker для frontend

Если нужен живой Vite dev server, удобнее держать базу в Docker, а backend и frontend запускать локально.

### 1. Запустить PostgreSQL

```bash
cp .env.example .env
docker compose up -d postgres
```

### 2. Запустить backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --reload
```

### 3. Запустить frontend

```bash
cd frontend
npm install
npm run dev
```

Локально:
- frontend dev server: обычно `http://localhost:5173`
- backend API: `http://localhost:8000`

Во время локальной разработки frontend проксирует `/api` и `/health` на backend.

## Bootstrap данных

По умолчанию проект не требует обязательного наличия больших CSV.

- В Docker используется `BOOTSTRAP_DATASET=auto`
- В таком режиме backend пытается загрузить:
  1. portal CSV
  2. synthetic dataset
  3. demo data

То есть приложение должно стартовать даже без файлов `СТЕ_20260403.csv` и `Контракты_20260403.csv`.

## Импорт реальных CSV

Если нужно загрузить реальные данные портала, положите рядом с корнем проекта:
- `СТЕ_20260403.csv`
- `Контракты_20260403.csv`

Затем выполните:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.import_portal_csv \
  --ste-csv ../СТЕ_20260403.csv \
  --contracts-csv ../Контракты_20260403.csv
```

Или через `Makefile` backend:

```bash
cd backend
make migrate
make seed-portal
```

Если нужен bootstrap именно через CSV при старте backend, выставьте:

```bash
BOOTSTRAP_DATASET=portal_csv
```

## Полезные команды

Из корня проекта:

```bash
make up
make down
make restart
make logs
make backend-logs
make frontend-logs
make ps
make build
```

Из `backend`:

```bash
make install
make db-up
make migrate
make seed
make seed-portal
make run
```

## Что важно знать

- Docker-конфигурация по умолчанию включает ML provider `local_ml` и `BOOTSTRAP_DATASET=auto`.
- Локальный backend без `.env` стартует с более консервативными дефолтами из кода.
- Demo-auth не требует пароля и подходит только для MVP и демо.
- Спецификация telemetry лежит в [backend/TELEMETRY_SPEC.md](./backend/TELEMETRY_SPEC.md).
- Большие CSV, `.env`, `backend/.venv` и кэш уже исключены через [`.gitignore`](./.gitignore).

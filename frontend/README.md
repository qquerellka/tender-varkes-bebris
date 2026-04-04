# Frontend

React + Vite приложение для search-first интерфейса.

## Локальная разработка

```bash
cd frontend
npm install
npm run dev
```

По умолчанию Vite поднимает dev server на `http://localhost:5173`.

## Требование для API

Для локальной разработки frontend ожидает backend на `http://localhost:8000` и проксирует туда:
- `/api`
- `/health`

Это настроено в [vite.config.ts](./vite.config.ts).

## Сборка

```bash
cd frontend
npm run build
```

## Docker

Из корня проекта:

```bash
cp .env.example .env
docker compose up --build frontend
```

В полном стеке frontend доступен на `http://localhost:3000`.

В Docker production-сборка отдается через `nginx`, а `/api` и `/health` проксируются в backend через [nginx.conf](./nginx.conf).

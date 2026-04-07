# Архитектура Backend

Этот документ описывает текущую структуру backend-части платформы поиска для закупочного портала.

## Назначение

Backend сейчас выступает как orchestration layer для search MVP.

Он отвечает за:
- публичный API
- хранение каталога и поведенческих данных
- baseline search pipeline
- сбор событий
- точку расширения под будущую ML-интеграцию

## Основные слои

### API layer

Находится в `app/api`.

Зона ответственности:
- роуты FastAPI
- валидация request/response
- wiring зависимостей
- маппинг HTTP-вызовов на сервисы

Текущие группы роутов:
- auth
- catalog
- search
- events
- profile
- user actions

### Demo auth layer

Находится в `app/auth`.

Зона ответственности:
- отдавать текущего actor для demo-режима
- изолировать временный demo identity mechanism от API-зависимостей

Текущая реализация:
- `auth/demo.py`
- поддерживает готовые demo-профили для заказчика и поставщика
- выбирается через `X-Demo-User-Id`

### Domain layer

Находится в `app/domain`.

Зона ответственности:
- search pipeline logic
- personalization logic
- обработка событий
- чтение каталога

Ключевые модули:
- `domain/auth`
- `domain/search`
- `domain/personalization`
- `domain/events`
- `domain/catalog`
- `domain/user_actions`

### Repository layer

Находится в `app/db/repositories`.

Зона ответственности:
- чтение и запись данных в PostgreSQL
- retrieval кандидатов
- lookup spell corrections и synonyms
- хранение search sessions и events

### Persistence layer

Находится в `app/db` и `alembic`.

Зона ответственности:
- SQLAlchemy models
- migrations
- DB sessions
- demo seed data

### Integration layer

Находится в `app/integrations/ml`.

Зона ответственности:
- контракт backend <-> ML
- изоляция будущего ML ranking implementation за адаптером

## Текущий Search Flow

1. Frontend вызывает `POST /api/v1/search`.
2. API route вызывает `SearchService`.
3. `SearchService`:
   - нормализует запрос
   - загружает spell corrections из БД
   - применяет исправления
   - обрабатывает неправильную раскладку
   - извлекает query terms
   - расширяет простые variants
   - загружает synonyms из БД
   - строит retrieval terms
4. `SearchRepository` достает кандидатов из PostgreSQL через:
   - `ILIKE`
   - `pg_trgm` similarity
   - матчинг по title, description и attributes
5. `SearchService` строит candidate scores через rule-based ranking.
6. `RankingProvider` сортирует кандидатов.
7. Backend сохраняет:
   - `search_session`
   - `search_submitted` event
8. Backend возвращает items и explainability metadata на frontend.

## Источники Данных

### Хранятся в PostgreSQL

- organizations
- users
- categories
- suppliers
- ste items
- purchase history
- search sessions
- search events
- user search profiles
- org search profiles
- synonyms
- spell corrections

### Пока остаются rule-based в коде

- stop words
- простые query term variants
- ranking weights
- explainability labels

### Пока остаются demo-specific

- выбор demo actor через environment-backed demo auth

## Персонализация

Текущая персонализация не ML-based, а profile-based.

Уже используются сигналы:
- top categories
- recent STE interactions
- top suppliers
- popular STE items внутри организации
- popular queries
- favorites / compare / cart

Backend использует их как ranking boosts.

Подробная спецификация event-модели и search telemetry лежит в [TELEMETRY_SPEC.md](./TELEMETRY_SPEC.md).

## Механизмы Качества Поиска

Текущее качество baseline search обеспечивается за счет:
- query normalization
- spell correction из БД
- correction неправильной раскладки
- synonym expansion из БД
- term-variant expansion
- `pg_trgm` retrieval
- rule-based scoring
- profile-based personalization

Это non-ML baseline, который должен оставаться рабочим и после появления ML.

## Контракт Для Frontend

Frontend сейчас зависит от:
- `/api/v1/search`
- `/api/v1/search/history`
- `/api/v1/search/suggestions`
- `/api/v1/search/spellcheck`
- `/api/v1/catalog/ste/{id}/related`
- `/api/v1/events`

Backend должен сохранять эти контракты, даже если ranking внутри улучшается.

## Готовность К ML

Backend уже устроен так, чтобы ML можно было встроить после retrieval.

Текущая точка интеграции:

`retrieval -> candidate set -> RankingProvider -> final ranked response`

Будущий путь:
- заменить `NoopRankingProvider` на `MlRankingProvider`
- не ломать orchestration и fallback behavior backend-а

Подробный контракт лежит в `ML_HANDOFF.md`.

## Fallback Подход

Backend должен продолжать работать даже без ML.

Это означает:
- retrieval должен быть самодостаточным
- ranking должен иметь rule-based fallback
- публичный API не должен падать при отсутствии ML

## Рекомендуемые Следующие Шаги

1. Дальше улучшать demo и QA-контур: документация, тесты, debug-экраны.
2. Ввести observability для качества поиска, warmup и fallback activation.
3. Расширить integration/API tests для auth, telemetry, profile и search.
4. Расширить search signals и quality metrics без изменения публичного API.

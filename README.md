# TIU Media Hub — бэкенд DAM

FastAPI · PostgreSQL · MinIO + nginx CDN · RabbitMQ (taskiq) · Qdrant · Infinity (CLIP) · Keycloak.

## Запуск

```bash
cp .env.example .env
docker compose up -d --build     # весь стек; первый старт Infinity качает модели (~1 ГБ)
```

| Сервис | Адрес |
|---|---|
| API (OpenAPI) | http://localhost:8000/docs |
| Keycloak | http://localhost:8081 (admin/admin) |
| CDN | http://localhost:8090 |
| MinIO console | http://localhost:9001 |
| RabbitMQ | http://localhost:15672 |

Пользователи realm (dev): `ivanov/ivanov`, `petrova/petrova`, `admin/admin` (роль admin).
Сервисный клиент: `tiu-media-hub-service` / `dev-service-secret` (роль `assets:read`).

Проверка стека: `uv run python -m tests.e2e.smoke`.

## Устройство

- `src/api` — HTTP: `/api/user/v1`, `/api/admin/v1`, `/api/client/v1`
- `src/core` — инфраструктура: auth DTO, Keycloak, БД, S3, CDN, Qdrant, Infinity, RabbitMQ
- `src/modules` — users, collections, media (загрузки и целостность), assets (версии, лицензии), tags, processing, search
- `src/worker` — taskiq: очереди `processing` (CPU) и `indexing` (эмбеддинги), планировщик обслуживания

Загрузка: SHA-256 считается в браузере, входит в подпись presigned URL (хранилище отклоняет подмену),
сверяется при подтверждении и повторно при обработке. Админ-эндпоинт проверяет целостность всего хранилища.

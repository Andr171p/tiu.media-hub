# Локальный запуск

Требования: Docker Desktop (Compose 2.24+), для работы вне Docker — Python 3.14 и [uv](https://docs.astral.sh/uv/),
ffmpeg в `PATH`.

## Весь стек одной командой

```bash
cp .env.example .env          # укажите VISION_API_KEY (ключ AITunnel)
docker compose up -d --build
```

Первый запуск скачивает модели CLIP (~1 ГБ) и Whisper в тома: `worker-ai` ждёт готовности Infinity.

| Сервис | Адрес |
|---|---|
| API, OpenAPI | http://localhost:8000/docs |
| CDN (nginx) | http://localhost:8090 |
| Keycloak | http://localhost:8081 (admin / admin) |
| RustFS (S3 / консоль) | http://localhost:9000 / http://localhost:9001 (dam / dam-dev-secret) |
| RabbitMQ | http://localhost:15672 (dam / dam) |
| Qdrant | http://localhost:6333/dashboard |
| Infinity, Whisper | http://localhost:7997, http://localhost:9010 |
| PostgreSQL | localhost:5433 (dam / dam) |

Dev-пользователи realm: `ivanov/ivanov`, `petrova/petrova`, `admin/admin` (глобальный администратор).
Сервисный клиент: `tiu-media-hub-service` / `dev-service-secret`.

Токен для curl:

```bash
curl -s -d grant_type=password -d client_id=tiu-media-hub-dev -d username=ivanov -d password=ivanov \
  http://localhost:8081/realms/tiu-media-hub/protocol/openid-connect/token | jq -r .access_token
```

## Разработка: инфраструктура в Docker, приложение на хосте

```bash
docker compose up -d postgres rabbitmq rustfs storage-init cdn keycloak qdrant infinity whisper
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
uv run taskiq worker src.infra.broker.media_tasks:media_broker
uv run taskiq worker src.infra.broker.ai_tasks:ai_broker
uv run python -m src.infra.outbox.relay
```

На Windows системный прокси может перехватывать `localhost`: задайте `NO_PROXY=localhost,127.0.0.1`.
Шрифты редактора на Windows — `EDITOR_FONT_REGULAR`/`EDITOR_FONT_BOLD` (см. `.env.example`).

## Проверки

```bash
uv run ruff format src && uv run ruff check src
uv run --with mypy mypy src
uv run pytest tests/integration      # против запущенного стека
```

Интеграционные тесты: загрузка → обработка → превью через CDN → поиск по фото и тексту;
права на закрытую коллекцию.

## Миграции

```bash
uv run alembic revision --autogenerate -m "описание"   # проверьте сгенерированный файл
uv run alembic upgrade head
```

Generated columns (`search_vector`) и функции `uuid_generate_v7()`, `dam_tags_text()` создаются вручную
в начальной миграции — autogenerate их не сравнивает.

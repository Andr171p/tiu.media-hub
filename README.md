# TIU Media Hub — бэкенд DAM ТИУ

Коллекции и права, версии, ИИ-описания и теги, умный поиск (естественный язык, по фото, по селфи, по речи),
распознавание людей на фото и видео, контент-порталы, серверный редактор изображений, лицензии,
комментарии с отметками областей и таймкодов, прокси-версии для видео.

FastAPI + [DDF](https://github.com/Andr171p/py-ddd-framework) · PostgreSQL · RustFS + nginx CDN ·
RabbitMQ (TaskIQ) · Qdrant · Infinity (CLIP) · OpenCV (лица) · Whisper · Keycloak · VLM (AITunnel / Ollama).

## Запуск

```bash
cp .env.example .env     # VISION_API_KEY — ключ AITunnel
docker compose up -d --build
```

API: http://localhost:8000/docs · пользователи: `ivanov/ivanov`, `petrova/petrova`, `admin/admin`.

GPU-сервер: `COMPOSE_PROFILES=gpu` в `.env` — см. [деплой](docs/operations/deploy.md).

## Документация

[docs/README.md](docs/README.md): архитектура, доменная модель, доступ, медиа, поиск, решения,
API для фронта, локальный запуск и деплой.

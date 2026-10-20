# Деплой на сервер (GPU)

Тот же `docker compose`, другой `.env`.

## Подготовка сервера

* Docker Engine + Compose 2.24+.
* NVIDIA-драйвер и [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html);
  проверка: `docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi`.
* Домен(ы) и TLS-терминация перед стеком (внешний nginx/Traefik).

## `.env` для сервера

```ini
COMPOSE_PROFILES=gpu                       # CUDA-образы Infinity и Whisper + Ollama

# VLM: локальная модель вместо AITunnel (скачивается сервисом ollama-pull при первом запуске)
VISION_BASE_URL=http://ollama:11434/v1
VISION_API_KEY=
VISION_MODEL=qwen3-vl:4b
OLLAMA_VISION_MODEL=qwen3-vl:4b
WHISPER_MODEL=small

# Публичные адреса (через TLS-прокси)
CDN_BASE_URL=https://media.example.ru
S3_PUBLIC_ENDPOINT_URL=https://media.example.ru
CDN_CORS_ORIGIN=https://dam.example.ru
API_CORS_ORIGINS='["https://dam.example.ru"]'
KEYCLOAK_PUBLIC_URL=https://id.example.ru
KEYCLOAK_ISSUER_URL=https://id.example.ru/realms/tiu-media-hub
KEYCLOAK_USER_CLIENT_IDS='["tiu-media-hub-web"]'

# Секреты — длинные случайные (openssl rand -hex 32)
POSTGRES_PASSWORD=...
KEYCLOAK_DB_PASSWORD=...
KEYCLOAK_ADMIN_PASSWORD=...
RABBIT_PASSWORD=...
S3_SECRET_KEY=...
CDN_SECRET=...
PORTAL_SECRET=...
QDRANT_API_KEY=...
```

Если на сервере уже работает Ollama из `tiu.llm-local`, можно не поднимать свою: укажите её адрес в
`VISION_BASE_URL` (с basic auth — через прокси) и скачайте vision-модель (`ollama pull qwen3-vl:4b`).
Текстовая `qwen2.5:3b` изображения не понимает.

## Запуск и обновление

```bash
git pull
docker compose up -d --build      # миграции применяются сервисом migrate перед стартом API
docker compose ps                 # все сервисы healthy / running, migrate и storage-init — exited (0)
```

## Обязательно для production

* **Не публиковать порты** инфраструктуры: оставить наружу только `cdn` (80) и `api` (8000) за TLS-прокси,
  Keycloak (8080) — за прокси на своём домене. Порты задаются в `docker/*.yml`; для сервера удобно
  вынести их в `compose.override.yml` с `ports: !reset []`.
* **Keycloak**: заменить `start-dev` на `start` (TLS на прокси: `--proxy-headers=xforwarded --http-enabled=true`),
  удалить клиент `tiu-media-hub-dev` и dev-пользователей, задать redirect URI и web origins фронта
  в клиенте `tiu-media-hub-web`, сменить секрет `tiu-media-hub-service`.
* **Масштабирование**: `MEDIA_WORKERS` (процессы перекодирования ≈ ядра CPU / 2), `AI_MAX_ASYNC_TASKS`;
  `scheduler` — строго один экземпляр, `relay` можно несколько.
* **Бэкапы**: PostgreSQL (`pg_dump` баз `dam` и `keycloak`), том `rustfs_data` (оригиналы).
  Производные, векторы Qdrant и кеш CDN восстанавливаются повторной обработкой
  (`POST /api/admin/v1/versions/{id}/reprocess`).
* **Ресурсы**: CPU-профиль Whisper медленный для длинных видео — на сервере используйте GPU-профиль.

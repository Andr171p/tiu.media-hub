# Один образ для API, воркеров, relay, планировщика и миграций: различается только команда запуска.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    FACES_MODELS_DIR=/app/models

# ffmpeg — метаданные, постеры и прокси видео/аудио; DejaVu — кириллица в тексте редактора; git — DDF из репозитория
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

# Модели лиц OpenCV Zoo (YuNet + SFace, ~40 МБ): в образе, чтобы не зависеть от сети при работе
ADD https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx \
    /app/models/

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN useradd --system --no-create-home app && chmod -R a+r /app/models
USER app

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

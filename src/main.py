"""ASGI-приложение TIU Media Hub. Запуск: ``uvicorn src.main:app``."""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

from src.api.errors import register_exception_handlers  # noqa: E402
from src.api.lifespan import lifespan  # noqa: E402
from src.api.routers import router  # noqa: E402


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(
        title="TIU Media Hub",
        version="1.0.0",
        description="DAM ТИУ: коллекции, версии, ИИ-теги, умный поиск, лица, порталы, редактор",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ApiConfig().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    register_exception_handlers(app)

    @app.get("/health", tags=["Health"], summary="Проверка доступности")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

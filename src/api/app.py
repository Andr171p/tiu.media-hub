import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ApiConfig
from .errors import register_exception_handlers
from .lifespan import lifespan as default_lifespan
from .routers import router

type Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(config: ApiConfig | None = None, *, lifespan: Lifespan = default_lifespan) -> FastAPI:
    config = config or ApiConfig()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = FastAPI(title=config.title, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    app.include_router(router)
    register_exception_handlers(app)

    @app.get("/health", tags=["Health"], summary="Проверка доступности")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


__all__ = ["create_app"]

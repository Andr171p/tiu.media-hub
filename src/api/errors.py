from typing import Any

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.core.auth import AuthenticationUnavailableError, UnauthorizedError
from src.core.common.exceptions import AppError

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errorCode": error_code, "message": message, "details": details},
        headers=headers,
    )


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)

    headers = None
    if isinstance(exc, UnauthorizedError):
        headers = {"WWW-Authenticate": 'Bearer error="invalid_token"'}
    elif isinstance(exc, AuthenticationUnavailableError):
        headers = {"Retry-After": "5"}

    return _error_response(exc.status_code, exc.error_code, exc.message, exc.details, headers)


async def _handle_integrity_error(_: Request, exc: Exception) -> JSONResponse:
    """Нарушение ограничения, обнаруженное при записи (гонка за уникальность и т.п.), — конфликт, а не 500."""

    assert isinstance(exc, IntegrityError)
    logger.warning("Integrity error: %s", exc.orig)
    return _error_response(HTTPStatus.CONFLICT, "conflict", "Operation conflicts with the current state.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(IntegrityError, _handle_integrity_error)


__all__ = ["register_exception_handlers"]

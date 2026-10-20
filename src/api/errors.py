from typing import Any

import logging
from http import HTTPStatus

from ddf.application.exceptions import ApplicationError
from ddf.domain.exceptions import DomainError
from ddf.infra.database.sqlalchemy.utils import get_constraint_name, is_unique_violation
from ddf.infra.integrations.keycloak import InvalidTokenError, KeycloakUnavailableError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    error_code: str,
    message: str | None,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errorCode": error_code.lower(), "message": message, "details": details},
        headers=headers,
    )


async def _handle_business_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError | DomainError)
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == HTTPStatus.UNAUTHORIZED else None
    return _error_response(exc.status_code, exc.error_code, exc.message, exc.details, headers)


async def _handle_integrity_error(_: Request, exc: Exception) -> JSONResponse:
    """Нарушения ограничений при записи — конфликт, а не 500."""

    assert isinstance(exc, IntegrityError)
    if is_unique_violation(exc):
        return _error_response(
            HTTPStatus.CONFLICT,
            "unique_constraint_violation",
            "Resource already exists.",
            get_constraint_name(exc),
        )

    logger.warning("Integrity error: %s", exc.orig)
    return _error_response(HTTPStatus.CONFLICT, "integrity_violation", "Operation violates data integrity.")


async def _handle_invalid_token(_: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        HTTPStatus.UNAUTHORIZED,
        "invalid_token",
        str(exc),
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


async def _handle_idp_unavailable(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("Keycloak is unavailable: %s", exc)
    return _error_response(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "identity_provider_unavailable",
        "Try again later.",
        headers={"Retry-After": "5"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, _handle_business_error)
    app.add_exception_handler(DomainError, _handle_business_error)
    app.add_exception_handler(IntegrityError, _handle_integrity_error)
    app.add_exception_handler(InvalidTokenError, _handle_invalid_token)
    app.add_exception_handler(KeycloakUnavailableError, _handle_idp_unavailable)


__all__ = ["register_exception_handlers"]

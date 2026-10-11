from http import HTTPStatus

from pydantic import JsonValue


class AppError(Exception):
    """Базовая ошибка приложения: несёт HTTP-статус и машиночитаемый код."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: JsonValue = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "not_found"


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "conflict"


class InvalidDataError(AppError):
    """Данные синтаксически корректны, но нарушают правила предметной области."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "invalid_data"


__all__ = ["AppError", "ConflictError", "InvalidDataError", "NotFoundError"]

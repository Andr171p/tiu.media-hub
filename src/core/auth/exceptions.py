from http import HTTPStatus

from src.core.common.exceptions import AppError


class UnauthorizedError(AppError):
    """Учётные данные отсутствуют, недействительны или не соответствуют контракту токена."""

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "unauthorized"


class PermissionDeniedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "permission_denied"


class AuthenticationUnavailableError(AppError):
    """Провайдер идентификации недоступен: токен нельзя проверить прямо сейчас."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "authentication_unavailable"


__all__ = ["AuthenticationUnavailableError", "PermissionDeniedError", "UnauthorizedError"]

from enum import StrEnum
from http import HTTPStatus
from uuid import UUID

from ddf.application.exceptions import ApplicationError
from pydantic import BaseModel, ConfigDict, Field

ADMIN_ROLE = "admin"
SERVICE_READ_ROLE = "assets:read"


class AuthType(StrEnum):
    USER = "user"
    SERVICE = "service"


class Auth(BaseModel):
    """Аутентифицированный субъект. Права на коллекции определяет наш бэкенд, а не Keycloak."""

    model_config = ConfigDict(frozen=True)

    class User(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: UUID
        username: str | None = None
        email: str | None = None
        full_name: str | None = None

    id: str = Field(description="sub для пользователя, client_id для сервиса")
    type: AuthType
    roles: frozenset[str] = Field(default_factory=frozenset)
    user: User | None = None

    @property
    def is_admin(self) -> bool:
        return self.type is AuthType.USER and ADMIN_ROLE in self.roles


class AuthUser(Auth):
    user: Auth.User

    @property
    def user_id(self) -> UUID:
        return self.user.id


class UnauthorizedError(ApplicationError):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "unauthorized"


class PermissionDeniedError(ApplicationError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "permission_denied"


__all__ = [
    "ADMIN_ROLE",
    "SERVICE_READ_ROLE",
    "Auth",
    "AuthType",
    "AuthUser",
    "PermissionDeniedError",
    "UnauthorizedError",
]

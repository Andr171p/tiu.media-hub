from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ADMIN_ROLE = "admin"
"""Роль клиента API в Keycloak: полный доступ ко всем коллекциям DAM."""

ASSETS_READ_ROLE = "assets:read"
"""Роль сервисного клиента: чтение всех коллекций и активов."""


class AuthType(StrEnum):
    """Тип аутентифицированного субъекта (роль — отдельное понятие, см. ``roles``)."""

    USER = "user"
    CLIENT = "client"


class Auth(BaseModel):
    """Аутентифицированный субъект: пользователь (PKCE) или сервис (Client Credentials)."""

    model_config = ConfigDict(frozen=True)

    class User(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: UUID = Field(description="Идентификатор пользователя Keycloak (sub)")
        # Формат почты проверяет Keycloak: строгая валидация здесь отвергла бы корпоративные домены
        email: str | None = Field(default=None, description="Электронная почта")
        email_verified: bool = Field(default=False, description="Подтверждена ли почта")
        username: str | None = Field(default=None, description="Логин")
        full_name: str | None = Field(default=None, description="ФИО")
        roles: frozenset[str] = Field(default_factory=frozenset, description="Роли клиента API")

    class Client(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: str = Field(min_length=1, description="Публичный идентификатор клиента (azp)")
        roles: frozenset[str] = Field(default_factory=frozenset, description="Роли клиента API")

    id: UUID = Field(description="Субъект токена (sub)")
    type: AuthType

    user: User | None = None
    client: Client | None = None


class AuthUser(Auth):
    """Аутентифицированный пользователь."""

    user: Auth.User

    @property
    def is_admin(self) -> bool:
        return ADMIN_ROLE in self.user.roles


class AuthClient(Auth):
    """Аутентифицированный сервис."""

    client: Auth.Client

    def has_role(self, role: str) -> bool:
        return role in self.client.roles


__all__ = ["ADMIN_ROLE", "ASSETS_READ_ROLE", "Auth", "AuthClient", "AuthType", "AuthUser"]

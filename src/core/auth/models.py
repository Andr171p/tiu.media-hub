from typing import Literal

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthType(StrEnum):
    USER = "user"
    CLIENT = "client"


class Auth(BaseModel):
    model_config = ConfigDict(frozen=True)

    class User(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: UUID
        email: EmailStr
        email_verified: bool = Field(default=False, description="Проверена ли почта пользователя")
        username: str | None = Field(default=None, description="Никнейм пользователя")
        full_name: str | None = Field(default=None, description="ФИО пользователя")
        roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")

    id: UUID
    type: AuthType

    user: User | None = None


class AuthUser(Auth):
    model_config = ConfigDict(frozen=True)

    type: Literal[AuthType.USER] = AuthType.USER

    user: Auth.User


class AuthClient(Auth):
    model_config = ConfigDict(frozen=True)

    type: Literal[AuthType.CLIENT] = AuthType.CLIENT

    class Client(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: str = Field(min_length=1, description="Публичный идентификатор клиента")
        roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")

    client: Client

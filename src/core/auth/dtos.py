from typing import Annotated

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AuthType(StrEnum):
    USER = "user"
    CLIENT = "client"


class CurrentUser(BaseModel):
    id: UUID = Field(description="Уникальный идентификатор")
    type: AuthType.USER = AuthType.USER

    username: str | None = Field(default=None, description="Никнейм пользователя")
    email: EmailStr | None = Field(default=None, description="Подтверждённая почта")
    full_name: str | None = Field(default=None, description="ФИО пользователя")
    roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")


class CurrentClient(BaseModel):
    type: AuthType.CLIENT = AuthType.CLIENT

    client_id: str = Field(description="Публичный идентификатор клиента")
    roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")


type CurrentAuth = Annotated[CurrentUser | CurrentClient, Field(discriminator="type")]

__all__ = ["CurrentAuth", "CurrentClient", "CurrentUser"]

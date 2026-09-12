from typing import Annotated, Literal

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthType(StrEnum):
    USER = "user"
    CLIENT = "client"


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Уникальный идентификатор")
    type: Literal[AuthType.USER] = AuthType.USER

    username: str | None = Field(default=None, description="Никнейм пользователя")
    email: EmailStr | None = Field(default=None, description="Почта пользователя")
    email_verified: bool = False
    full_name: str | None = Field(default=None, description="ФИО пользователя")
    roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")


class Client(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal[AuthType.CLIENT] = AuthType.CLIENT

    client_id: str = Field(min_length=1, description="Публичный идентификатор клиента")
    roles: frozenset[str] = Field(default_factory=frozenset, description="Назначенные роли")


type Auth = Annotated[User | Client, Field(discriminator="type")]

__all__ = ["Auth", "Client", "User"]

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Аутентифицированный пользователь делающий запрос."""

    id: UUID = Field(description="Уникальный идентификатор пользователя (от провайдера).")
    username: str | None = Field(
        default=None,
        description="Никнейм пользователя.",
        examples=["ivanov.ii"],
    )
    first_name: str | None = Field(
        default=None, description="Имя пользователя.", examples=["Иван"],
    )
    last_name: str | None = Field(
        default=None, description="Фамилия пользователя", examples=["Иванов"],
    )
    email: EmailStr | None = Field(description="Подтверждённая почта пользователя.")
    roles: frozenset[str] = Field(
        default_factory=frozenset, description="Роли назначенный пользователю.",
    )

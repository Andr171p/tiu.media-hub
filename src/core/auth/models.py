from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Аутентифицированный пользователь делающий запрос."""

    id: UUID = Field(description="Уникальный идентификатор пользователя (от провайдера).")
    username: str = Field(description="Никнейм пользователя.", examples=["some_user"])
    email: EmailStr | None = Field(description="Подтверждённая почта пользователя.")
    roles: frozenset[str] = Field(
        default_factory=frozenset, description="Роли назначенный пользователю.",
    )

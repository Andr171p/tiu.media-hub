from uuid import UUID

from pydantic import Field

from src.core.common.schemas import Schema


class UserResponse(Schema):
    id: UUID
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    display_name: str = Field(description="Имя для отображения")


class CurrentUserResponse(UserResponse):
    roles: list[str] = Field(description="Роли клиента API")
    is_admin: bool = Field(description="Администратор DAM")

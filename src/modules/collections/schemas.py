from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field, NonNegativeInt

from src.core.common.schemas import PageParams, Schema
from src.core.common.types import Description, Str255
from src.modules.users.schemas import UserResponse

from .access import Action
from .models import MemberRole, Visibility
from .settings import CollectionSettings


class CollectionScope(StrEnum):
    ALL = "all"
    """Все доступные: свои, где я участник, и публичные."""

    MINE = "mine"
    """Где я владелец или участник."""

    PUBLIC = "public"


class CollectionFilters(PageParams):
    scope: CollectionScope = CollectionScope.ALL
    query: str | None = Field(default=None, max_length=255, description="Поиск по названию")


class CreateCollectionDTO(Schema):
    name: Str255
    description: Description | None = None
    visibility: Visibility = Visibility.PRIVATE


class UpdateCollectionDTO(Schema):
    """Частичное обновление: передаются только изменяемые поля."""

    name: Str255 | None = None
    description: Description | None = None
    visibility: Visibility | None = None


class CollectionStats(Schema):
    asset_count: NonNegativeInt = 0
    cover_url: str | None = Field(default=None, description="Миниатюра последнего актива")


class CollectionResponse(Schema):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime

    name: str
    description: str | None
    visibility: Visibility
    owner: UserResponse
    settings: CollectionSettings

    role: str = Field(description="Роль текущего пользователя: viewer, member, moderator, owner")
    permissions: list[Action] = Field(description="Разрешённые действия текущего пользователя")
    stats: CollectionStats = Field(default_factory=CollectionStats)


class AddMemberDTO(Schema):
    user_id: UUID
    role: MemberRole = MemberRole.MEMBER


class UpdateMemberDTO(Schema):
    role: MemberRole


class MemberResponse(Schema):
    user: UserResponse
    role: MemberRole
    created_at: AwareDatetime


__all__ = [
    "AddMemberDTO",
    "CollectionFilters",
    "CollectionResponse",
    "CollectionScope",
    "CollectionStats",
    "CreateCollectionDTO",
    "MemberResponse",
    "UpdateCollectionDTO",
    "UpdateMemberDTO",
]

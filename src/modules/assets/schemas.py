from typing import Annotated, Literal

from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, StringConstraints

from src.core.common.schemas import PageParams, Schema
from src.core.common.types import Description, FileName, Str255
from src.modules.tags.models import TagSource
from src.modules.users.schemas import UserResponse

from .compliance import Issue
from .licensing import License
from .meta import AssetKind, VersionMeta
from .models import AssetStatus, VersionStatus

type TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class CreateAssetDTO(Schema):
    object_id: UUID = Field(description="Загруженный и подтверждённый объект")
    original_filename: FileName
    title: Str255 | None = Field(default=None, description="По умолчанию — имя файла без расширения")
    description: Description | None = None
    custom_meta: dict[str, JsonValue] = Field(default_factory=dict)
    license: License | None = None
    tags: list[TagName] = Field(default_factory=list, max_length=50)


class UpdateAssetDTO(Schema):
    """Частичное обновление: передаются только изменяемые поля. ``null`` очищает необязательное поле."""

    title: Str255 | None = None
    description: Description | None = None
    custom_meta: dict[str, JsonValue] | None = None
    license: License | None = None
    status: AssetStatus | None = None


class CreateVersionDTO(Schema):
    object_id: UUID
    original_filename: FileName
    source_version_id: UUID | None = Field(
        default=None,
        description="Исходная версия, если файл получен её редактированием",
    )


class SetTagsDTO(Schema):
    tags: list[TagName] = Field(max_length=50)


class AssetFilters(PageParams):
    kind: AssetKind | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    tag: str | None = Field(default=None, description="Имя тега")
    query: str | None = Field(default=None, max_length=255, description="Подстрока названия")


class Renditions(Schema):
    thumbnail: str | None = Field(default=None, description="URL миниатюры")
    preview: str | None = Field(default=None, description="URL превью (с водяным знаком коллекции)")


class VersionResponse(Schema):
    id: UUID
    number: int
    status: VersionStatus
    error: str | None
    original_filename: str
    size_bytes: int
    sha256: str
    content_type: str = Field(description="Фактический MIME-тип, если файл уже обработан")
    meta: VersionMeta | None
    issues: list[Issue]
    source_version_id: UUID | None
    created_by: UserResponse
    created_at: AwareDatetime
    processed_at: AwareDatetime | None
    renditions: Renditions
    is_current: bool


class AssetTagResponse(Schema):
    name: str
    source: TagSource
    confidence: float | None = None


class AssetResponse(Schema):
    id: UUID
    collection_id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime

    title: str
    description: str | None
    kind: AssetKind
    status: AssetStatus
    author: UserResponse
    custom_meta: dict[str, JsonValue]
    license: License | None
    tags: list[AssetTagResponse]

    current_version: VersionResponse | None = Field(description="Актуальная готовая версия")
    pending_version: VersionResponse | None = Field(
        default=None,
        description="Более новая версия, которая обрабатывается или не прошла проверку",
    )
    issues: list[Issue] = Field(description="Замечания по лицензии и метаданным")
    can_edit: bool


class DownloadResponse(Schema):
    url: str
    filename: str
    kind: Literal["original", "preview"] = Field(
        description="Оригинал доступен участникам коллекции; остальным — превью с водяным знаком",
    )


__all__ = [
    "AssetFilters",
    "AssetResponse",
    "AssetTagResponse",
    "CreateAssetDTO",
    "CreateVersionDTO",
    "DownloadResponse",
    "Renditions",
    "SetTagsDTO",
    "UpdateAssetDTO",
    "VersionResponse",
]

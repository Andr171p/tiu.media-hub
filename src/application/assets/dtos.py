from typing import Annotated, Literal

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, PositiveInt, StringConstraints

from src.application.dtos import CamelModel
from src.domain.assets import (
    AssetKind,
    License,
    LicenseStatus,
    LicenseType,
    Period,
    UsageChannel,
)
from src.domain.collections import MetadataValue, Permission

type Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
type Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ProcessingStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class PeriodDTO(CamelModel):
    start: date | None = None
    end: date | None = None


class LicenseDTO(CamelModel):
    type: LicenseType
    holder: str | None = Field(default=None, max_length=500, description="Правообладатель")
    period: PeriodDTO = Field(default_factory=PeriodDTO, description="Срок действия")
    territories: list[str] = Field(
        default_factory=list, description="Территории (пусто — без ограничений)", examples=[["RU", "KZ"]]
    )
    channels: list[UsageChannel] = Field(default_factory=list, description="Носители (пусто — любые)")
    restrictions: str | None = Field(default=None, max_length=5000, description="Прочие ограничения")

    def to_domain(self) -> License:
        return License(
            type=self.type,
            holder=self.holder,
            period=Period(start=self.period.start, end=self.period.end),
            territories=frozenset(self.territories),
            channels=frozenset(self.channels),
            restrictions=self.restrictions,
        )


class LicenseResponse(LicenseDTO):
    status: LicenseStatus


class FileDTO(CamelModel):
    name: str
    content_type: str
    size: int


class VersionMetaDTO(CamelModel):
    width: int | None = None
    height: int | None = None
    duration: float | None = Field(default=None, description="Секунды")
    frame_rate: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    page_count: int | None = None
    captured_at: datetime | None = None
    camera: str | None = None


class RenditionUrls(CamelModel):
    """Временные ссылки CDN. Ссылка стабильна в пределах окна подписи, поэтому браузер её кеширует."""

    thumbnail: str | None = None
    preview: str | None = None
    video: str | None = None
    audio: str | None = None


class VersionResponse(CamelModel):
    id: UUID
    number: int
    file: FileDTO
    status: ProcessingStatus
    processing_error: str | None
    meta: VersionMetaDTO | None
    urls: RenditionUrls
    source_version_id: UUID | None = Field(description="Версия-источник (редактор)")
    note: str | None
    created_by: UUID
    created_at: datetime


class AssetSummary(CamelModel):
    id: UUID
    collection_id: UUID
    title: str
    kind: AssetKind
    tags: list[str]
    license_status: LicenseStatus | None = Field(description="Статус лицензии на сегодня; None — не указана")
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    trashed_at: datetime | None
    version: VersionResponse = Field(description="Текущая версия")


class AssetResponse(AssetSummary):
    description: str | None
    caption: str | None = Field(description="Описание, сгенерированное ИИ")
    metadata: dict[str, MetadataValue]
    license: LicenseResponse | None
    version_count: int
    permissions: list[Permission] = Field(description="Права текущего пользователя в коллекции актива")


class UpdateAssetDTO(CamelModel):
    """Частичное обновление: явный ``null`` очищает описание и лицензию."""

    title: Title | None = None
    description: str | None = Field(default=None, max_length=10000)
    tags: list[Tag] | None = Field(default=None, max_length=100)
    metadata: dict[str, MetadataValue] | None = None
    license: LicenseDTO | None = None


class MoveAssetDTO(CamelModel):
    collection_id: UUID


class AssetListQuery(CamelModel):
    collection_id: UUID | None = None
    kinds: list[AssetKind] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    person_id: UUID | None = None
    created_by: UUID | None = None
    license: LicenseStatus | Literal["none"] | None = None
    trashed: bool = False
    sort: Literal["created_at", "updated_at"] = "created_at"
    cursor: str | None = None
    size: PositiveInt = Field(default=50, le=200)


class DownloadResponse(CamelModel):
    url: str
    expires_in: int = Field(description="Секунды")

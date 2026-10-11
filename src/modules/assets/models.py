"""
Asset ── логическая единица контента в коллекции (название, метаданные, лицензия, теги)
 └── AssetVersion ── неизменяемая версия файла: оригинал (StoredObject) и технические метаданные
       └── Rendition ── производные для просмотра: миниатюра и превью
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import TEXT, CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, SoftDeleteMixin
from src.core.database.types import DatetimeTzNull, PydanticJSONB, TextNull
from src.modules.media.models import StoredObject
from src.modules.tags.models import AssetTag
from src.modules.users.models import User

from .compliance import Issue
from .licensing import License
from .meta import AssetKind, VersionMeta


class AssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class RenditionKind(StrEnum):
    THUMBNAIL = "thumbnail"
    """Без водяного знака: сетка и эмбеддинг для поиска."""

    PREVIEW = "preview"
    """Крупное превью для просмотра, с водяным знаком коллекции."""


class Asset(SoftDeleteMixin, Base):
    __tablename__ = "assets"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="RESTRICT"))
    title: Mapped[str]
    description: Mapped[TextNull]
    kind: Mapped[AssetKind]
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.ACTIVE)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)

    custom_meta: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)
    license: Mapped[License | None] = mapped_column(PydanticJSONB(License))

    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="SET NULL", use_alter=True),
    )

    current_version: Mapped[AssetVersion | None] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
        lazy="raise",
    )
    author: Mapped[User] = relationship(lazy="raise")
    tags: Mapped[list[AssetTag]] = relationship(lazy="raise", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_assets_collection_id_created_at", "collection_id", "created_at"),)


class AssetVersion(Base):
    __tablename__ = "asset_versions"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    number: Mapped[int]
    object_id: Mapped[UUID] = mapped_column(ForeignKey("stored_objects.id", ondelete="RESTRICT"))
    original_filename: Mapped[str]
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    source_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="SET NULL"),
        comment="Версия, из которой получена эта (правка в редакторе)",
    )

    status: Mapped[VersionStatus] = mapped_column(default=VersionStatus.PROCESSING, index=True)
    error: Mapped[TextNull]
    attempts: Mapped[int] = mapped_column(default=0, comment="Запусков обработки")
    processed_at: Mapped[DatetimeTzNull]

    meta: Mapped[VersionMeta | None] = mapped_column(PydanticJSONB(VersionMeta))
    issues: Mapped[list[Issue]] = mapped_column(PydanticJSONB(list[Issue]), default=list)
    extracted_text: Mapped[str | None] = mapped_column(
        TEXT,
        deferred=True,
        comment="Текст документа для полнотекстового поиска",
    )

    object: Mapped[StoredObject] = relationship(lazy="raise")
    creator: Mapped[User] = relationship(lazy="raise")
    renditions: Mapped[list[Rendition]] = relationship(lazy="raise", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("asset_id", "number"),
        UniqueConstraint("asset_id", "object_id"),
        CheckConstraint("number > 0", name="number_positive"),
    )


class Rendition(Base):
    __tablename__ = "renditions"

    version_id: Mapped[UUID] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"))
    kind: Mapped[RenditionKind]
    storage_key: Mapped[str] = mapped_column(unique=True)
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    width: Mapped[int]
    height: Mapped[int]

    __table_args__ = (UniqueConstraint("version_id", "kind"),)


__all__ = ["Asset", "AssetStatus", "AssetVersion", "Rendition", "RenditionKind", "VersionStatus"]

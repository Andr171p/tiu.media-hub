from __future__ import annotations

from typing import Any

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.common.models import Base
from src.core.common.types import FloatNull, IntNull, StrUnique, TextNull


class AssetType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class AssetStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    ARCHIVED = "archived"
    DELETED = "deleted"


class DerivativeType(StrEnum):
    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"
    WATERMARKED = "watermarked"


class AssetVersion(Base):
    """Версия оригинального файла медиа-ресурса."""

    __tablename__ = "asset_versions"

    asset: Mapped[Asset] = relationship(back_populates="versions")

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), unique=False)
    version: Mapped[int]
    creator_id: Mapped[UUID]

    storage_key: Mapped[str]
    original_filename: Mapped[str]
    mime_type: Mapped[str]
    size: Mapped[int]

    # Опциональные метаданные
    width: Mapped[IntNull]
    height: Mapped[IntNull]
    duration: Mapped[FloatNull]

    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    checksum: Mapped[str]

    __table_args__ = (UniqueConstraint("asset_id", "version", name="uq_asset_version"),)


class AssetDerivative(Base):
    """Производный файл, созданный системой из версии актива."""

    asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.id"), unique=False,
    )

    type_: Mapped[DerivativeType]
    storage_key: Mapped[StrUnique]
    mime_type: Mapped[str]

    size: Mapped[int]
    width: Mapped[IntNull]
    height: Mapped[IntNull]

    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (UniqueConstraint("asset_version_id", "type_", name="uq_asset_derivative"),)


class Asset(Base):
    """Логический медиа актив, доступный пользователям медиатеки."""

    __tablename__ = "assets"

    title: Mapped[str]
    description: Mapped[TextNull]

    type_: Mapped[AssetType]
    status: Mapped[AssetStatus]

    creator_id: Mapped[UUID]
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id"), nullable=True,
    )

    versions: Mapped[list[AssetVersion]] = relationship(back_populates="asset")

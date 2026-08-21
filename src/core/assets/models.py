from __future__ import annotations

from typing import Any

from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeFloat
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.common.models import Base
from src.core.common.types import FloatNull, IntNull, StrUnique, TextNull

from .enums import AssetStatus, AssetType, DerivativeType


class ImageMeta(BaseModel):
    """Метаданные изображения."""

    camera: str | None = Field(None, description="Модель камеры.")
    iso: int | None = Field(None, description="Время создания в ISO формате.")
    aperture: str | None = Field(None, description="Диафрагма объектива.")
    focal_length: str | None = Field(None, description="Фокусное расстояние.")


class VideoMeta(BaseModel):
    """Метаданные видео."""

    codec: str | None = Field(None, description="Codec видео.", exclude=["AV1", "VP9 "])
    fps: float | None = Field(None, description="Частота кадров в секунду.")
    bitrate: int | None = Field(None, description="Битрейт исходного видео.")
    duration: NonNegativeFloat | None = Field(None, description="Длительность в секундах.")


class AssetVersion(Base):
    """Версия оригинального файла медиа-ресурса."""

    __tablename__ = "asset_versions"

    asset: Mapped[Asset] = relationship(back_populates="versions")
    derivatives: Mapped[list[AssetDerivative]] = relationship(
        back_populates="asset_version", cascade="all, delete-orphan",
    )

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), unique=False)
    version: Mapped[int]
    author_id: Mapped[UUID | None] = mapped_column(nullable=True)

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
    asset_version: Mapped[AssetVersion] = relationship(back_populates="derivatives")

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

    type_: Mapped[AssetType | None] = mapped_column(nullable=True)
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.PENDING)

    author_id: Mapped[UUID | None] = mapped_column(nullable=True)
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id"), nullable=True, default=None,
    )

    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset",
        foreign_keys="AssetVersion.asset_id",
        cascade="all, delete-orphan",
    )

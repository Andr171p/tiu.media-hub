"""
Asset
 ├── UploadSession
 │     └── Object
 │
 └── AssetVersion
       ├── Object
       └── AssetDerivative
             └── Object
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base
from src.core.database.types import PydanticJSONB, StrNull, StrUnique, TextNull

from .meta import AssetMeta


class AssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class UploadStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class Asset(Base):
    """Логическая единица цифрового контента."""

    __tablename__ = "assets"

    collection_id: Mapped[UUID]

    title: Mapped[str]
    description: Mapped[TextNull]
    custom_meta: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    status: Mapped[AssetStatus]
    author_id: Mapped[UUID]

    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset",
        foreign_keys="AssetVersion.asset_id",
        cascade="all, delete-orphan",
    )
    uploads: Mapped[list[UploadSession]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class UploadSession(Base):
    """Поток загрузки медиа актива."""

    __tablename__ = "upload_sessions"

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        index=True,
    )
    object_id: Mapped[UUID] = mapped_column(
        ForeignKey("objects.id", ondelete="RESTRICT"),
        unique=True,
    )

    status: Mapped[UploadStatus] = mapped_column(default=UploadStatus.PENDING)
    filename: Mapped[str]
    uploaded_by: Mapped[UUID]

    declared_mime_type: Mapped[str]
    declared_size: Mapped[int]

    asset: Mapped[Asset] = relationship(back_populates="uploads")
    object: Mapped[Object] = relationship()
    version: Mapped[AssetVersion | None] = relationship(
        back_populates="upload",
        uselist=False,
    )


class AssetVersion(Base):
    """Версия медиа актива."""

    __tablename__ = "asset_versions"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    object_id: Mapped[UUID] = mapped_column(ForeignKey("objects.id", ondelete="RESTRICT"))
    upload_id: Mapped[UUID] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="RESTRICT"),
        unique=True,
    )

    number: Mapped[int]
    original_filename: Mapped[str]
    status: Mapped[VersionStatus] = mapped_column(default=VersionStatus.PROCESSING)

    meta: Mapped[AssetMeta | None] = mapped_column(PydanticJSONB(AssetMeta), nullable=True)
    raw_meta: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    asset: Mapped[Asset] = relationship(back_populates="versions", foreign_keys=[asset_id])
    upload: Mapped[UploadSession] = relationship(back_populates="version")
    object: Mapped[Object] = relationship()
    derivatives: Mapped[list[AssetDerivative]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("asset_id", "number", name="uq_asset_version_number"),
    )


class AssetDerivative(Base):
    """Производная от конкретной версии медиа актива."""

    __tablename__ = "asset_derivative"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="CASCADE"),
        index=True,
    )
    variant: Mapped[str]
    object_id: Mapped[UUID] = mapped_column(ForeignKey("object.id", ondelete="RESTRICT"))

    status: Mapped[...]

    object: Mapped[Object] = relationship()
    version: Mapped[AssetVersion] = relationship(back_populates="derivatives")

    __table_args__ = (
        UniqueConstraint("version_id", "variant", name="uq_derivative_version_variant"),
    )


class Object(Base):
    """
    Физический объект в объектном хранилище.

    Запись может быть создана до непосредственной загрузки объекта.
    Технические характеристики заполняются после inspection.
    """

    __tablename__ = "objects"

    storage_key: Mapped[StrUnique]
    mime_type: Mapped[StrNull]
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    checksum: Mapped[StrNull]

    __table_args__ = (Index("ix_object_checksum", "checksum"),)

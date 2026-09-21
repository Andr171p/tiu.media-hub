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


class AssetVersion(Base):
    """Версия медиа актива."""

    __tablename__ = "asset_versions"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    object_id: Mapped[UUID]

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

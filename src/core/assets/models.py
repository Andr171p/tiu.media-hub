"""
Asset
 └── AssetVersion
       ├── StoredObject
       └── AssetDerivative
             └── StoredObject
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base
from src.core.database.types import PydanticJSONB, TextNull

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
    custom_meta: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, default=dict)

    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.ACTIVE)
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
        UniqueConstraint("asset_id", "object_id", name="uq_asset_version_object"),
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

    version: Mapped[AssetVersion] = relationship(back_populates="derivatives")

    __table_args__ = (
        UniqueConstraint("version_id", "variant", name="uq_derivative_version_variant"),
    )

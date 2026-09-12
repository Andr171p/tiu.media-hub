from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base
from src.core.database.types import PydanticJSONB, StrUnique, TextNull

from .meta import AssetMeta


class AssetStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Asset(Base):
    __tablename__ = "assets"

    collection_id: Mapped[UUID]

    title: Mapped[str]
    description: Mapped[TextNull]

    status: Mapped[AssetStatus]
    created_by: Mapped[UUID]

    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id", use_alter=True),
        nullable=True,
    )
    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset",
        foreign_keys="AssetVersion.asset_id",
        cascade="all, delete-orphan",
    )


class AssetVersion(Base):
    __tablename__ = "asset_versions"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    number: Mapped[int]
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))

    original_filename: Mapped[str]
    status: Mapped[...]
    uploaded_by: Mapped[UUID | None] = mapped_column(nullable=True)

    meta: Mapped[AssetMeta | None] = mapped_column(PydanticJSONB(AssetMeta), nullable=True)
    raw: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONB, nullable=True, default=None)
    custom_meta: Mapped[dict[str, JsonValue] | None] = mapped_column(
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
    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"))

    status: Mapped[...]

    version: Mapped[AssetVersion] = relationship(back_populates="derivatives")


class Source(Base):
    """Физический первоисточник файла в хранилище."""

    __tablename__ = "sources"

    storage_key: Mapped[StrUnique]
    mime_type: Mapped[str]
    size_bytes: Mapped[int]
    checksum: Mapped[str]

    __table_args__ = (Index("ix_source_checksum", "checksum"),)

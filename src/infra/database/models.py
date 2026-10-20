"""
ORM-модели PostgreSQL. Value objects домена хранятся в JSONB, перечисления — строками.
Полнотекстовые векторы — generated columns (русская морфология).
"""

from typing import Any

from datetime import datetime
from uuid import UUID

from ddf.infra.database.sqlalchemy import Base, EntityMixin
from ddf.infra.outbox.sqlalchemy import OutboxMessageOrm
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

# Неизменяемая обёртка над array_to_string: нужна для generated column (создаётся в миграции)
TAGS_TEXT_FUNCTION = "dam_tags_text"


class UserOrm(EntityMixin, Base):
    __tablename__ = "users"

    username: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    full_name: Mapped[str | None] = mapped_column(String(500))


class CollectionOrm(EntityMixin, Base):
    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(index=True)
    visibility: Mapped[str] = mapped_column(String(16))
    upload_policy: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metadata_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)


class CollectionMemberOrm(EntityMixin, Base):
    __tablename__ = "collection_members"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(16))

    __table_args__ = (UniqueConstraint("collection_id", "user_id", name="uq_collection_members_user"),)


class AssetOrm(EntityMixin, Base):
    __tablename__ = "assets"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[UUID]
    description: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default="{}")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="{}")
    license: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    current_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.id", use_alter=True, deferrable=True, initially="DEFERRED")
    )
    version_count: Mapped[int] = mapped_column(Integer)

    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
            f"setweight(to_tsvector('russian', {TAGS_TEXT_FUNCTION}(tags)), 'A') || "
            "setweight(to_tsvector('russian', coalesce(caption, '')), 'B') || "
            "setweight(to_tsvector('russian', coalesce(description, '')), 'B')",
            persisted=True,
        ),
    )

    __table_args__ = (
        Index("ix_assets_collection_id_created_at", "collection_id", "created_at"),
        Index("ix_assets_tags", "tags", postgresql_using="gin"),
        Index("ix_assets_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_assets_deleted_at", "deleted_at", postgresql_where=text("deleted_at IS NOT NULL")),
    )


class AssetVersionOrm(EntityMixin, Base):
    __tablename__ = "asset_versions"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    file_key: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    created_by: Mapped[UUID]
    source_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)

    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    renditions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("asset_id", "number", name="uq_asset_versions_number"),)


class UploadOrm(EntityMixin, Base):
    __tablename__ = "uploads"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    created_by: Mapped[UUID]
    file_key: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    multipart_id: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TranscriptOrm(Base):
    __tablename__ = "transcripts"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str | None] = mapped_column(String(16))
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('russian', text)", persisted=True)
    )

    __table_args__ = (Index("ix_transcripts_search_vector", "search_vector", postgresql_using="gin"),)


class PersonOrm(EntityMixin, Base):
    __tablename__ = "people"

    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID]


class FaceOrm(EntityMixin, Base):
    __tablename__ = "faces"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"), index=True)
    box: Mapped[dict[str, Any]] = mapped_column(JSONB)
    timecodes: Mapped[list[float]] = mapped_column(ARRAY(Float), server_default="{}")
    person_id: Mapped[UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    assigned_by: Mapped[UUID | None]


class CommentOrm(EntityMixin, Base):
    __tablename__ = "comments"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    version_id: Mapped[UUID] = mapped_column(ForeignKey("asset_versions.id", ondelete="CASCADE"))
    author_id: Mapped[UUID]
    text: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    anchor: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None]

    __table_args__ = (Index("ix_comments_asset_id_created_at", "asset_id", "created_at"),)


class SelectionOrm(EntityMixin, Base):
    __tablename__ = "selections"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(index=True)
    shared: Mapped[bool] = mapped_column(Boolean)
    asset_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), server_default="{}")


class PortalOrm(EntityMixin, Base):
    __tablename__ = "portals"

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(index=True)
    theme: Mapped[dict[str, Any]] = mapped_column(JSONB)
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    access: Mapped[str] = mapped_column(String(16))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    allow_download: Mapped[bool] = mapped_column(Boolean)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "TAGS_TEXT_FUNCTION",
    "AssetOrm",
    "AssetVersionOrm",
    "Base",
    "CollectionMemberOrm",
    "CollectionOrm",
    "CommentOrm",
    "FaceOrm",
    "OutboxMessageOrm",
    "PersonOrm",
    "PortalOrm",
    "SelectionOrm",
    "TranscriptOrm",
    "UploadOrm",
    "UserOrm",
]

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base
from src.core.database.types import PydanticJSONB, TextNull

from .policies import UploadPolicy


class CollectionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MemberRole(StrEnum):
    """Роль участника внутри коллекции."""

    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class Collection(Base):
    __tablename__ = "collections"

    name: Mapped[str]
    description: Mapped[TextNull]

    owner_id: Mapped[UUID]
    status: Mapped[CollectionStatus] = mapped_column(default=CollectionStatus.ACTIVE)

    settings: Mapped[CollectionSettings] = relationship(
        back_populates="collection",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    members: Mapped[list[CollectionMember]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class CollectionSettings(Base):
    __tablename__ = "collection_settings"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=True)
    version: Mapped[int] = mapped_column(default=1)

    upload_policy: Mapped[UploadPolicy] = mapped_column(PydanticJSONB(UploadPolicy))
    processing_policy: Mapped[...] = mapped_column(PydanticJSONB(...))

    collection: Mapped[Collection] = relationship(back_populates="settings")


class CollectionMember(Base):
    __tablename__ = "collection_members"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=False)
    user_id: Mapped[UUID]
    role: Mapped[MemberRole]

    collection: Mapped[Collection] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("collection_id", "user_id", name="uq_collection_user"),
    )

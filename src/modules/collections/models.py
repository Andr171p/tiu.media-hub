from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, SoftDeleteMixin
from src.core.database.types import PydanticJSONB, TextNull
from src.modules.users.models import User

from .settings import CollectionSettings


class Visibility(StrEnum):
    PUBLIC = "public"
    """Просмотр доступен всем вошедшим пользователям."""

    PRIVATE = "private"
    """Только владелец и участники."""


class MemberRole(StrEnum):
    MEMBER = "member"
    """Просмотр, загрузка, редактирование своих активов."""

    MODERATOR = "moderator"
    """Плюс редактирование любых активов, участники и настройки коллекции."""


class Collection(SoftDeleteMixin, Base):
    """Граница доступа и политик: участники, схема метаданных, водяной знак, правила загрузки."""

    __tablename__ = "collections"

    name: Mapped[str]
    description: Mapped[TextNull]
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    visibility: Mapped[Visibility] = mapped_column(default=Visibility.PRIVATE)
    settings: Mapped[CollectionSettings] = mapped_column(
        PydanticJSONB(CollectionSettings),
        default=CollectionSettings,
    )

    owner: Mapped[User] = relationship(lazy="raise")


class CollectionMember(Base):
    __tablename__ = "collection_members"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole]

    user: Mapped[User] = relationship(lazy="raise")

    __table_args__ = (UniqueConstraint("collection_id", "user_id"),)


__all__ = ["Collection", "CollectionMember", "MemberRole", "Visibility"]

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.database.types import StrNull


class TagSource(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    """Назначен автотегированием (zero-shot классификация эмбеддингом изображения)."""


class Tag(Base):
    """
    Тег словаря. Свободные теги создаются пользователями; теги с ``auto_assign``
    курирует администратор, и только их назначает автотегирование.
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(
        unique=True, comment="Нормализованное имя: нижний регистр, без лишних пробелов"
    )
    auto_assign: Mapped[bool] = mapped_column(default=False, index=True)
    prompt: Mapped[StrNull] = mapped_column(comment="Описание для автотегирования, если имени недостаточно")


class AssetTag(Base):
    __tablename__ = "asset_tags"

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    source: Mapped[TagSource] = mapped_column(default=TagSource.MANUAL)
    confidence: Mapped[float | None] = mapped_column(comment="Уверенность автотегирования, 0..1")

    tag: Mapped[Tag] = relationship(lazy="raise")

    __table_args__ = (UniqueConstraint("asset_id", "tag_id"),)


__all__ = ["AssetTag", "Tag", "TagSource"]

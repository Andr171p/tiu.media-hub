from __future__ import annotations

from typing import Literal

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeFloat, PositiveInt
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.consts import DEFAULT_MAX_FILE_SIZE
from src.core.common.models import Base
from src.core.common.types import ListStr, PydanticJSONB, TextNull


class Collection(Base):
    __tablename__ = "collections"

    name: Mapped[str]
    description: Mapped[TextNull]

    owner_id: Mapped[UUID]
    is_active: Mapped[bool] = mapped_column(default=True)

    settings: Mapped[CollectionSettings] = relationship(
        back_populates="collection",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    members: Mapped[list[CollectionMember]] = relationship(back_populates="collection")


class ImageSizeSettings(BaseModel):
    """Настройки генерации деривативов (миниатюр) с сохранением пропорций."""

    width: PositiveInt | None = Field(default=None, description="Ширина в пикселях.")
    height: PositiveInt | None = Field(default=None, description="Высота в пикселях.")
    quality: int = Field(default=80, ge=1, le=100, description="Качество сжатия JPEG/WebP.")


class Position(BaseModel):
    """Координаты для позиционирования водяного знака."""

    x_percent: NonNegativeFloat = Field(
        default=5.0,
        le=100.0,
        description="Смещение по X в % от ширины.",
    )
    y_percent: NonNegativeFloat = Field(
        default=5.0,
        le=100.0,
        description="Смещение по Y в % от высоты.",
    )


class WatermarkSettings(BaseModel):
    """Настройки для водяного знака."""

    is_enabled: bool = Field(default=False, description="Доступно ли наложение водяного знака.")
    type: Literal["text", "image"] = Field(default="text", description="Тип водяного знака.")

    value: str | None = Field(
        default=None,
        description="Текст знака или ссылка на изображение.",
        examples=["https://tiu.storage/watermarks/logo.png", "Какой-то текст"],
    )
    opacity: NonNegativeFloat = Field(
        default=0.5,
        le=1.0,
        description="Прозрачность от 0.0 до 1.0.",
    )

    position: Position = Field(description="Координаты водяного знака.")


class CollectionSettings(Base):
    __tablename__ = "collection_settings"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=True)

    allowed_extensions: Mapped[ListStr]
    max_file_size: Mapped[int] = mapped_column(default=DEFAULT_MAX_FILE_SIZE)

    thumbnail: Mapped[ImageSizeSettings] = mapped_column(PydanticJSONB(ImageSizeSettings))
    preview: Mapped[ImageSizeSettings] = mapped_column(PydanticJSONB(ImageSizeSettings))
    watermark: Mapped[WatermarkSettings] = mapped_column(PydanticJSONB(WatermarkSettings))

    collection: Mapped[Collection] = relationship(back_populates="settings")


class MemberRole(StrEnum):
    """Роль участника внутри коллекции."""

    OWNER = "owner"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class CollectionMember(Base):
    __tablename__ = "collection_members"

    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=False)
    user_id: Mapped[UUID]
    role: Mapped[MemberRole]

    collection: Mapped[Collection] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("collection_id", "user_id", name="uq_collection_user"),
    )

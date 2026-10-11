"""Технические метаданные версии: извлекаются из файла при обработке и не редактируются вручную."""

from typing import Annotated, Literal

from datetime import datetime
from enum import StrEnum

from pydantic import Field, NonNegativeInt, PositiveInt

from src.core.common.schemas import Schema


class AssetKind(StrEnum):
    IMAGE = "image"
    DOCUMENT = "document"
    OTHER = "other"


_DOCUMENT_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/rtf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
    },
)
_DOCUMENT_MIME_PREFIXES = (
    "text/",
    "application/vnd.openxmlformats-officedocument.",
    "application/vnd.oasis.opendocument.",
)


def kind_of(mime_type: str) -> AssetKind:
    if mime_type.startswith("image/"):
        return AssetKind.IMAGE
    if mime_type in _DOCUMENT_MIME_TYPES or mime_type.startswith(_DOCUMENT_MIME_PREFIXES):
        return AssetKind.DOCUMENT
    return AssetKind.OTHER


class EmbeddedMetadata(Schema):
    """Сведения, записанные в самом файле (EXIF, XMP, свойства PDF): используются для проверки прав."""

    title: str | None = None
    description: str | None = None
    creator: str | None = Field(default=None, description="Автор (EXIF Artist, dc:creator, PDF Author)")
    copyright: str | None = Field(default=None, description="Правообладатель (EXIF Copyright, dc:rights)")
    usage_terms: str | None = Field(default=None, description="Условия использования (xmpRights:UsageTerms)")
    web_statement: str | None = Field(default=None, description="Ссылка на условия (xmpRights:WebStatement)")
    keywords: list[str] = Field(default_factory=list)
    captured_at: datetime | None = Field(default=None, description="Дата съёмки или создания")
    camera: str | None = None
    software: str | None = None
    has_location: bool = Field(default=False, description="Есть GPS-координаты")


class ImageMeta(Schema):
    kind: Literal[AssetKind.IMAGE] = AssetKind.IMAGE
    mime_type: str
    format: str | None = None
    width: PositiveInt
    height: PositiveInt
    mode: str = Field(description="Цветовая модель PIL: RGB, RGBA, CMYK, L…")
    has_alpha: bool = False
    dpi: tuple[float, float] | None = None
    icc_profile: str | None = Field(default=None, description="Описание встроенного ICC-профиля")
    frames: PositiveInt = Field(default=1, description="Кадров (анимация, многостраничный TIFF)")
    embedded: EmbeddedMetadata = Field(default_factory=EmbeddedMetadata)


class DocumentMeta(Schema):
    kind: Literal[AssetKind.DOCUMENT] = AssetKind.DOCUMENT
    mime_type: str
    page_count: NonNegativeInt | None = None
    has_text_layer: bool | None = None
    is_encrypted: bool | None = None
    embedded: EmbeddedMetadata = Field(default_factory=EmbeddedMetadata)


class OtherMeta(Schema):
    kind: Literal[AssetKind.OTHER] = AssetKind.OTHER
    mime_type: str


type VersionMeta = Annotated[ImageMeta | DocumentMeta | OtherMeta, Field(discriminator="kind")]

__all__ = [
    "AssetKind",
    "DocumentMeta",
    "EmbeddedMetadata",
    "ImageMeta",
    "OtherMeta",
    "VersionMeta",
    "kind_of",
]

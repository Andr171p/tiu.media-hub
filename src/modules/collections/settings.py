"""Настройки коллекции: хранятся одним JSONB-документом, поэтому расширяются без миграций схемы."""

from typing import Annotated, Literal, Self

import hashlib
from enum import StrEnum
from fnmatch import fnmatchcase
from uuid import UUID

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from src.core.common.schemas import Schema

_DEFAULT_MAX_FILE_SIZE = 200 * 1024 * 1024

DEFAULT_ALLOWED_MIME_TYPES = frozenset(
    {
        "image/*",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.*",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.oasis.opendocument.*",
        "application/rtf",
        "text/plain",
        "text/csv",
    },
)

type MimePattern = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[\w.+-]+/(?:\*|[\w.+-]+\*?)$"),
    Field(examples=["image/*", "application/pdf"]),
]


class UploadPolicy(Schema):
    """Какие файлы принимает коллекция. Проверяется по заявленному, а затем по фактическому MIME."""

    allowed_mime_types: set[MimePattern] = Field(
        default_factory=lambda: set(DEFAULT_ALLOWED_MIME_TYPES),
        min_length=1,
        description="Маски разрешённых MIME-типов",
    )
    max_file_size: PositiveInt = Field(
        default=_DEFAULT_MAX_FILE_SIZE, description="Максимальный размер, байт"
    )

    def allows(self, mime_type: str) -> bool:
        return any(fnmatchcase(mime_type.lower(), pattern) for pattern in self.allowed_mime_types)


# =================================================================================================
# Кастомные метаданные
# =================================================================================================


class MetadataFieldType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    CHOICE = "choice"


type FieldKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
type FieldLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
type ChoiceOption = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MetadataField(Schema):
    """Поле кастомных метаданных: по описанию поля клиент строит форму, сервер валидирует значения."""

    key: FieldKey = Field(description="Ключ в custom_meta", examples=["event_date"])
    label: FieldLabel = Field(description="Подпись в интерфейсе", examples=["Дата мероприятия"])
    type: MetadataFieldType
    required: bool = False
    description: str | None = Field(default=None, max_length=500)
    options: list[ChoiceOption] = Field(default_factory=list, description="Варианты для типа choice")
    multiple: bool = Field(default=False, description="Несколько значений (только choice)")

    @model_validator(mode="after")
    def _check_options(self) -> Self:
        if self.type is MetadataFieldType.CHOICE:
            if not self.options:
                raise ValueError("Choice field requires options.")
            if len(set(self.options)) != len(self.options):
                raise ValueError("Choice options must be unique.")
        elif self.options or self.multiple:
            raise ValueError("Only choice fields can have options or multiple values.")
        return self


class LicensePolicy(Schema):
    required: bool = Field(default=False, description="Актив без лицензии считается нарушением (error)")


# =================================================================================================
# Водяной знак
# =================================================================================================


class WatermarkPlacement(Schema):
    """
    Положение задаётся на клиенте в относительных координатах, поэтому не зависит от размера кадра.
    ``x``/``y`` — центр знака, ``scale`` — ширина знака относительно ширины изображения.
    """

    x: float = Field(default=0.85, ge=0, le=1)
    y: float = Field(default=0.9, ge=0, le=1)
    scale: float = Field(default=0.2, gt=0, le=1)
    opacity: float = Field(default=0.5, ge=0.05, le=1)


class ImageWatermark(Schema):
    type: Literal["image"] = "image"
    object_id: UUID = Field(description="Загруженное изображение знака (PNG с прозрачностью)")
    placement: WatermarkPlacement = Field(default_factory=WatermarkPlacement)


class TextWatermark(Schema):
    type: Literal["text"] = "text"
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] = Field(
        examples=["© ТИУ 2026"],
    )
    color: Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")] = "#FFFFFF"
    placement: WatermarkPlacement = Field(default_factory=WatermarkPlacement)


type Watermark = Annotated[ImageWatermark | TextWatermark, Field(discriminator="type")]


def watermark_fingerprint(watermark: ImageWatermark | TextWatermark | None) -> str:
    """Короткий отпечаток настроек: входит в ключ превью, чтобы смена знака не попала в кеш CDN."""

    if watermark is None:
        return "plain"
    return hashlib.sha256(watermark.model_dump_json().encode()).hexdigest()[:10]


class CollectionSettings(Schema):
    upload: UploadPolicy = Field(default_factory=UploadPolicy)
    metadata_fields: list[MetadataField] = Field(default_factory=list, max_length=50)
    license: LicensePolicy = Field(default_factory=LicensePolicy)
    watermark: Watermark | None = Field(default=None, description="Знак на превью для просмотра")

    @model_validator(mode="after")
    def _check_unique_keys(self) -> Self:
        keys = [field.key for field in self.metadata_fields]
        if len(set(keys)) != len(keys):
            raise ValueError("Metadata field keys must be unique.")
        return self


__all__ = [
    "CollectionSettings",
    "ImageWatermark",
    "LicensePolicy",
    "MetadataField",
    "MetadataFieldType",
    "TextWatermark",
    "UploadPolicy",
    "Watermark",
    "WatermarkPlacement",
    "watermark_fingerprint",
]

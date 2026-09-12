from typing import Annotated

from pydantic import BaseModel, Field, PositiveInt

from src.core.assets.enums import AssetType

MimePattern = Annotated[
    str,
    Field(
        min_length=3,
        pattern=r"^[\w.+-]+/(?:\*|[\w.+-]+)$",
        description="Маска MIME-типа файла",
        examples=["image/*", "video/mp4", "audio/*", "application/pdf"],
    )
]


class FileSizePolicy(BaseModel):
    """Политика для ограничения размера загружаемых файлов."""

    default_bytes: PositiveInt = Field(description="Максимальный размер по умолчанию в байтах")
    overrides: dict[AssetType, int] = Field(
        default_factory=dict,
        description="Переопределения максимального размера файла для отдельных типов медиаконтента"
    )


class UploadPolicy(BaseModel):
    """Политика загрузки файлов в коллекцию."""

    allowed_mime_types: set[MimePattern] = Field(
        min_length=1,
        description="Набор разрешённых MIME-типов",
    )
    file_size: FileSizePolicy = Field(description="Ограничения размера загружаемых файлов.")
    allow_unknown_media: bool = Field(
        default=False,
        description="Разрешено ли хранение неопознанных файлов",
    )

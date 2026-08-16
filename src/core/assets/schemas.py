from typing import Annotated, Any, Literal

from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)

from .models import AssetType, AssetVersionStatus, DerivativeType

# =================================================================================================
# Custom pydantic annotations
# =================================================================================================

FilePathStr = Annotated[
    str,
    Field(
        pattern=r'^[^\\/:*?"<>|]+$',
        description="Корректное имя файла без запрещенных символов",
    ),
]

FileSize = Annotated[NonNegativeInt, Field(description="Размер файла в байтах.")]

MimeType = Annotated[
    str, Field(description="Mime тип файла.", examples=["image/png", "audio/mpeg"]),
]

# =================================================================================================
# Metadata DTOs
# =================================================================================================


class ImageMeta(BaseModel):
    """Метаданные изображения."""

    camera: str | None = Field(None, description="Модель камеры.")
    iso: int | None = Field(None, description="Время создания в ISO формате.")
    aperture: str | None = Field(None, description="Диафрагма объектива.")
    focal_length: str | None = Field(None, description="Фокусное расстояние.")


class VideoMeta(BaseModel):
    """Метаданные видео."""

    codec: str | None = Field(None, description="Codec видео.", exclude=["AV1", "VP9 "])
    fps: float | None = Field(None, description="Частота кадров в секунду.")
    bitrate: int | None = Field(None, description="Битрейт исходного видео.")
    duration: float | None = Field(None, description="Длительность в секундах.")


# =================================================================================================
# Create & Update DTOs
# =================================================================================================

class AssetCreate(BaseModel):
    """Создание медиа актива."""

    title: str = Field(
        description="Название медиа актива.", examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(None, description="Описание контекста.")
    type: AssetType = Field(description="Тип контента.")


class AssetUpdate(BaseModel):
    """Редактирование информации об медиа активе."""

    title: str = Field(
        description="Название медиа актива.", examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(None, description="Описание контекста.")


class AssetVersionUpload(BaseModel):
    """Инициация процесса загрузки версии медиа актива."""

    filename: FilePathStr
    mime_type: MimeType


# =================================================================================================
# Response DTOs
# =================================================================================================

class AssetResponse(BaseModel):
    """"""


class AssetDerivativeResponse(BaseModel):
    """Производная от версии медиа актива."""

    cdn_url: HttpUrl | None = Field(None, description="Ссылка на CDN.")
    mime_type: MimeType
    size: FileSize

    width: NonNegativeInt | None = Field(None, description="Ширина в пикселях.")
    height: NonNegativeInt | None = Field(None, description="Высота в пикселях.")

    meta: dict[str, Any] = Field(default_factory=dict, description="Произвольные метаданные.")


class AssetOriginal(BaseModel):
    filename: FilePathStr
    mime_type: MimeType
    size: FileSize

    cdn_url: HttpUrl | None = Field(None, description="Ссылка на CDN.")

    width: NonNegativeInt | None = Field(None, description="Ширина в пикселях.")
    height: NonNegativeInt | None = Field(None, description="Высота в пикселях.")
    duration: NonNegativeFloat | None = Field(None, description="Длительность в секундах.")


class AssetVersionResponse(BaseModel):
    """Версия медиа актива."""

    id: UUID = Field(description="Уникальный идентификатор версии.")
    created_at: AwareDatetime = Field(description="Дата создания.")
    updated_at: AwareDatetime = Field(description="Дата последнего обновления.")

    version: PositiveInt = Field(description="Номер версии (счётчик).")
    author_id: UUID | None = Field(None, description="Тот, кто загрузил актив.")

    original: AssetOriginal = Field(description="Исходный актив.")

    meta: dict[str, Any] = Field(
        default_factory=dict, description="Метаданные в зависимости от типа актива.",
    )
    derivatives: dict[DerivativeType, AssetDerivativeResponse] = Field(
        default_factory=dict, description="Производные от текущей версии.",
    )


class AssetVersionUploadResponse(BaseModel):
    """Данные для прямой загрузки версии медиа актива в S3."""

    version_id: UUID = Field(description="Уникальный идентификатор версии.")
    version: PositiveInt = Field(description="Номер текущей версии.")
    status: AssetVersionStatus = Field(description="Статус загрузки версии.")

    upload_url: HttpUrl = Field(description="Временный URL для прямой загрузки.")
    method: Literal["PUT"] = Field(default="PUT", description="HTTP метод для загрузки в S3.")
    expires_in: NonNegativeInt = Field(description="Время жизни URL в секундах.")

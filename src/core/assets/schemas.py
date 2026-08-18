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

from .models import AssetStatus, AssetType, AssetVersionStatus, DerivativeType

# =================================================================================================
# Custom pydantic annotations
# =================================================================================================

FilePathStr = Annotated[
    str,
    Field(
        pattern=r'^[^\\/:*?"<>|]+$',
        description="Корректное имя файла без запрещенных символов",
        examples=["image.jpg"]
    ),
]

FileSize = Annotated[
    NonNegativeInt,
    Field(description="Размер файла в байтах.", examples=[5242880]),
]

MimeType = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        description="Mime тип файла.",
        examples=["image/png", "audio/mpeg"]
    ),
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
# API request DTOs
# =================================================================================================


class FileMeta(BaseModel):
    """Метаданные файла полученные с клиента."""

    filename: FilePathStr
    mime_type: MimeType
    size: FileSize


class UploadInfo(BaseModel):
    """Данные для прямой загрузки S3."""

    url: HttpUrl = Field(description="Временный URL для прямой загрузки.")
    method: Literal["PUT"] = Field(
        default="PUT",
        frozen=True,
        description="HTTP метод для загрузки в S3.",
    )
    expires_in: NonNegativeInt = Field(description="Время жизни URL в секундах.")


class AssetVersionUploadResponse(BaseModel):
    """Данные для прямой загрузки версии медиа актива в S3."""

    asset_id: UUID = Field(description="Уникальный идентификатор медиа актива.")
    version_id: UUID = Field(description="Уникальный идентификатор версии.")
    version: PositiveInt = Field(description="Номер текущей версии.")
    status: AssetVersionStatus = Field(description="Статус загрузки версии.")

    upload: UploadInfo = Field(description="Информация для загрузки актива.")


class AssetCreate(BaseModel):
    """DTO для создания записи медиа актива."""

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Название медиа-актива.",
        examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Описание и контекст медиа-актива.",
    )
    type_: AssetType = Field(description="Тип медиа актива (определяется системой).")


class AssetUploadRequest(AssetCreate):
    """Запрос на создание нового медиа-актива."""

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Название медиа-актива.",
        examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Описание и контекст медиа-актива.",
    )
    file: FileMeta = Field(description="Метаданные файла полученные с клиента.")


class AssetUpdate(BaseModel):
    """Запрос на изменение метаданных медиа-актива."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Новое название медиа-актива.",
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Новое описание медиа-актива.",
    )
    status: AssetStatus | None = Field(None, description="Статус медиа актива.")


class AssetVersionCreate(BaseModel):
    """DTO для создания версии медиа-актива."""

    asset_id: UUID
    version: PositiveInt

    storage_key: str
    original_filename: FilePathStr
    mime_type: MimeType
    size: FileSize

    status: AssetVersionStatus = AssetVersionStatus.UPLOADING


class AssetVersionUpdate(BaseModel):
    """Обновление состояния версии актива."""

    status: AssetVersionStatus | None = Field(None, description="Статус загрузки версии.")
    checksum: str | None = Field(None, description="Контрольная сумма (хеш).")


# =================================================================================================
# Create & Update DTOs
# =================================================================================================


class AssetUpload(BaseModel):
    filename: FilePathStr
    mime_type: MimeType


class AssetCreate(BaseModel):
    """Создание медиа актива."""

    title: str = Field(
        description="Название медиа актива.", examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(None, description="Описание контекста.")
    type: AssetType = Field(description="Тип контента.")

    upload: AssetUpload


class AssetVersionCreate(BaseModel):
    asset_id: UUID
    version: PositiveInt
    author_id: UUID | None = None
    storage_key: str
    original_filename: FilePathStr
    mime_type: str
    size: NonNegativeInt


# =================================================================================================
# Response DTOs
# =================================================================================================


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

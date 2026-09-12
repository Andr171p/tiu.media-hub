from typing import Annotated, Literal

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, PositiveInt


class AssetType(StrEnum):
    """Обобщённый тип медиа актива."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    OTHER = "other"


class ImageMeta(BaseModel):
    type: Literal[AssetType.IMAGE] = AssetType.IMAGE

    width: PositiveInt = Field(description="Ширина в пикселях")
    height: PositiveInt = Field(description="Высота в пикселях")

    color_space: str | None = Field(
        default=None,
        description="Цветовое пространство (например, sRGB, AdobeRGB)",
    )
    has_alpha: bool | None = Field(default=None, description="Наличие альфа-канала (прозрачности)")

    dpi_x: float | None = Field(default=None, description="Разрешение по горизонтали (DPI)")
    dpi_y: float | None = Field(default=None, description="Разрешение по вертикали (DPI)")


class VideoMeta(BaseModel):
    type: Literal[AssetType.VIDEO] = AssetType.VIDEO

    width: PositiveInt | None = Field(default=None, description="Ширина кадра в пикселях")
    height: PositiveInt | None = Field(default=None, description="Высота кадра в пикселях")

    duration_ms: PositiveInt = Field(description="Длительность видео в миллисекундах")

    frame_rate: Decimal | None = Field(default=None, description="Частота кадров (FPS)")
    bit_rate: PositiveInt | None = Field(default=None, description="Общий битрейт в бит/с")

    video_codec: str | None = Field(
        default=None,
        description="Кодек видеопотока",
        examples=["h264", "hevc"],
    )
    audio_codec: str | None = Field(
        default=None,
        description="Кодек аудиопотока",
        examples=["aac", "mp3"]
    )


class AudioMeta(BaseModel):
    type: Literal[AssetType.AUDIO] = AssetType.AUDIO

    duration_ms: PositiveInt = Field(description="Длительность аудио в миллисекундах")

    bit_rate: PositiveInt | None = Field(default=None, description="Битрейт в бит/с")
    sample_rate_hz: PositiveInt | None = Field(
        default=None,
        description="Частота дискретизации в Гц",
    )
    channels: PositiveInt | None = Field(default=None, description="Количество аудио каналов")

    codec: str | None = Field(default=None, description="Аудиокодек (например, flac, opus)")


class DocumentMeta(BaseModel):
    type: Literal[AssetType.DOCUMENT] = AssetType.DOCUMENT

    page_count: PositiveInt | None = Field(
        default=None,
        description="Количество страниц в документе",
    )
    has_text_layer: bool | None = Field(
        default=None,
        description="Наличие текстового слоя для поиска (OCR / native text)",
    )
    language: str | None = Field(
        default=None,
        description="Основной язык документа в формате ISO 639-1 (например, ru, en)",
        examples=["ru", "en"],
    )
    is_encrypted: bool | None = Field(
        default=None,
        description="Защищен ли документ паролем или DRM",
    )


type AssetMeta = Annotated[
    ImageMeta
    | VideoMeta
    | AudioMeta
    | DocumentMeta,
    Field(discriminator="type"),
]

__all__ = ["AssetMeta", "AssetType"]

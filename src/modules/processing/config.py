from pathlib import Path

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROCESSING_")

    thumbnail_size: PositiveInt = Field(default=480, description="Длинная сторона миниатюры, px")
    preview_size: PositiveInt = Field(default=1920, description="Длинная сторона превью, px")
    webp_quality: int = Field(default=82, ge=1, le=100)

    max_image_pixels: PositiveInt = Field(
        default=250_000_000,
        description="Защита от decompression bomb: изображения больше не открываются",
    )
    max_attempts: PositiveInt = Field(default=3, description="Запусков обработки до отметки об ошибке")
    stale_after: PositiveInt = Field(
        default=10 * 60,
        description="Через сколько секунд незавершённая обработка считается потерянной и перезапускается",
    )

    text_excerpt_chars: PositiveInt = Field(
        default=20_000, description="Сколько текста документа индексировать"
    )
    spool_max_size: PositiveInt = Field(
        default=64 * 1024 * 1024,
        description="Файлы до этого размера обрабатываются в памяти, крупнее — через временный файл",
    )
    watermark_font_path: Path = Field(
        default=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        description="TrueType-шрифт с кириллицей для текстового водяного знака",
    )

from pydantic import BaseModel, Field


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

from pydantic import Field, HttpUrl, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class InfinityConfig(BaseSettings):
    """Сервер эмбеддингов Infinity с CLIP/SigLIP-моделью: тексты и изображения в одном пространстве."""

    model_config = SettingsConfigDict(env_prefix="INFINITY_")

    url: HttpUrl = Field(default=HttpUrl("http://localhost:7997"), description="Адрес Infinity")
    model: str = Field(
        default="google/siglip-base-patch16-256-multilingual",
        description="Модель (--model-id Infinity). Должна понимать русский язык",
    )
    dimensions: PositiveInt = Field(default=768, description="Размерность эмбеддинга модели")
    batch_size: PositiveInt = Field(default=16, description="Элементов в одном запросе")
    timeout: PositiveFloat = Field(default=60, description="Таймаут запроса в секундах")

from pydantic import Field, HttpUrl, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class InfinityConfig(BaseSettings):
    """
    Сервер эмбеддингов Infinity. Текст и изображения кодируются разными моделями,
    обученными в одном векторном пространстве: так текстовый запрос сравним с картинкой.
    """

    model_config = SettingsConfigDict(env_prefix="INFINITY_")

    url: HttpUrl = Field(default=HttpUrl("http://localhost:7997"), description="Адрес Infinity")
    image_model: str = Field(default="openai/clip-vit-base-patch32", description="Модель изображений")
    text_model: str = Field(
        default="sentence-transformers/clip-ViT-B-32-multilingual-v1",
        description="Модель текста в пространстве image_model. Должна понимать русский язык",
    )
    dimensions: PositiveInt = Field(default=512, description="Размерность общего пространства")
    batch_size: PositiveInt = Field(default=16, description="Элементов в одном запросе")
    timeout: PositiveFloat = Field(default=60, description="Таймаут запроса в секундах")

from pydantic import Field, HttpUrl, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    url: HttpUrl = Field(default=HttpUrl("http://localhost:6333"), description="URL Qdrant (HTTP API)")
    api_key: SecretStr | None = Field(default=None, description="API ключ Qdrant")
    timeout: PositiveInt = Field(default=30, description="Таймаут запросов в секундах")

    prefix: str = Field(default="dam", description="Префикс имён коллекций")
    generation: PositiveInt = Field(
        default=1,
        description="Поколение индекса: увеличивается при смене модели эмбеддингов или её размерности",
    )
    bm25_language: str = Field(default="russian", description="Язык стемминга и стоп-слов BM25")

    def collection_name(self, name: str) -> str:
        return f"{self.prefix}_{name}_g{self.generation}"

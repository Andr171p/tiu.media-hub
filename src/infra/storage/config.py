from pydantic import Field, HttpUrl, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    """S3-совместимое хранилище (RustFS). Оригиналы и производные — в разных бакетах."""

    model_config = SettingsConfigDict(env_prefix="S3_")

    endpoint_url: HttpUrl = Field(default=HttpUrl("http://localhost:9000"), description="Адрес для бэкенда")
    public_endpoint_url: HttpUrl = Field(
        default=HttpUrl("http://localhost:8090"),
        description="Адрес для браузера: им подписываются presigned URL (через nginx)",
    )
    region: str = "us-east-1"
    access_key: str = "dam"
    secret_key: SecretStr = SecretStr("dam-dev-secret")
    originals_bucket: str = "dam-originals"
    renditions_bucket: str = "dam-renditions"


class CdnConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDN_")

    base_url: HttpUrl = Field(
        default=HttpUrl("http://localhost:8090"), description="Публичный адрес nginx CDN"
    )
    secret: SecretStr = Field(
        default=SecretStr("dev-cdn-secret"), description="Общий секрет с nginx secure_link"
    )
    url_ttl: PositiveInt = Field(default=3600, description="Окно подписи ссылки, секунды")


__all__ = ["CdnConfig", "StorageConfig"]

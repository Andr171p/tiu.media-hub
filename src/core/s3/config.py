from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="S3_")

    endpoint_url: str = Field(
        default="http://localhost:9000",
        description="Адрес S3 API для самого приложения (внутренняя сеть)",
    )
    public_endpoint_url: str | None = Field(
        default=None,
        description=(
            "Адрес S3 API, доступный браузеру: им подписываются presigned URL. "
            "По умолчанию совпадает с endpoint_url"
        ),
    )
    access_key: str = Field(description="Access key")
    secret_key: SecretStr = Field(description="Secret key")
    region: str = "us-east-1"
    bucket: str = Field(description="Бакет с оригиналами и производными")

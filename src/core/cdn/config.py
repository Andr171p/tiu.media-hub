from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class CdnConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDN_")

    base_url: str = Field(default="http://localhost:8090", description="Публичный адрес CDN (nginx)")
    path_prefix: str = Field(default="/media", description="Префикс location с secure_link в nginx")
    secret: SecretStr = Field(description="Общий с nginx секрет для подписи ссылок (secure_link_md5)")
    link_ttl: PositiveInt = Field(
        default=60 * 60,
        description=(
            "Окно жизни ссылки в секундах. Срок округляется до окна, поэтому в его пределах "
            "URL не меняется и кешируется браузером"
        ),
    )

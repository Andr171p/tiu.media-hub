from pydantic import AnyHttpUrl, Field, NonNegativeFloat, NonNegativeInt, SecretStr
from pydantic_settings import BaseSettings


class SrvBaseConfig(BaseSettings):
    """Базовая конфигурация для HTTP клиента."""

    base_url: AnyHttpUrl = Field(
        description="Базовый URL адрес без слешей",
        examples=["https://pizdatyy.site.com"],
    )
    token_url: AnyHttpUrl = Field()

    client_id: str = Field(description="Публичный идентификатор клиента")
    client_secret: SecretStr = Field(description="Пароль клиента (никому не показывать)")

    timeout: NonNegativeFloat = Field(
        default=10.0,
        description="Таймаут HTTP-запросов в секундах",
    )
    token_rotate_margin: NonNegativeFloat = Field(
        default=30.0,
        ge=0,
        description="За сколько секунд до истечения access token его необходимо обновить",
    )

    verify_ssl: bool = Field(default=True, description="Проверять ли сертификат")

    keepalive_timeout: NonNegativeFloat = Field(
        default=30.0,
        description="Время жизни простаивающего соединения",
    )
    pool_limit: NonNegativeInt = Field(default=100, description="Ограничение пула соединений")

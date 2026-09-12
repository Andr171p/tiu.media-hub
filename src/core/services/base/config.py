from pydantic import (
    AnyHttpUrl,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    SecretStr,
)
from pydantic_settings import BaseSettings


class SrvBaseConfig(BaseSettings):
    """Базовые настройки для HTTP клиента."""

    base_url: AnyHttpUrl = Field(description="Базовый URL без слешей")
    token_url: AnyHttpUrl = Field(description="URL для аутентификации")

    client_id: str = Field(description="Публичный идентификатор клиента")
    client_secret: SecretStr = Field(min_length=1, description="Секрет клиента (пароль)")
    scope: str | None = Field(default=None, description="")

    timeout: PositiveFloat = Field(default=10.0, description="Время ожидания запроса")
    token_rotate_margin: NonNegativeFloat = Field(
        default=30.0,
        description="Погрешность для обновления токена",
    )

    keepalive_timeout: PositiveFloat = 30
    pool_limit: PositiveInt = Field(description="Лимит пула HTTP соединений")

    verify_ssl: bool = Field(default=True, description="Проверять ли сертификаты")

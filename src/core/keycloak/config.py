from typing import Literal

from pydantic import AnyHttpUrl, Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_")

    issuer_url: AnyHttpUrl = Field(
        description="Базовый URL издателя токенов (Keycloak Realm URL)",
    )
    jwks_url: AnyHttpUrl = Field(
        description=(
            "URL эндпоинта Keycloak с публичными ключами (JWKS) "
            "для проверки криптографической подписи токенов"
        ),
        examples=["http://localhost:8081/realms/tiu-media-hub/protocol/openid-connect/certs"]
    )

    audience: str = Field(min_length=1, description="Идентификатор (аудитория) текущего API")
    algorithms: tuple[Literal["RS256", "RS384", "RS512"], ...] = Field(
        default=("RS256",),
        min_length=1,
        description="Разрешенные алгоритмы асимметричного шифрования",
    )

    user_client_ids: frozenset[str] = Field(
        description="Client ID приложений, через которые авторизуются пользователи",
    )
    service_client_ids: frozenset[str] = Field(
        description="Client ID доверенных сервисов для межсервисного взаимодействия",
    )

    jwks_cache_ttl: PositiveFloat = Field(
        default=300.0,
        description="Время жизни кэша публичных ключей JWKS в секундах",
    )
    jwks_refresh_cooldown: PositiveFloat = Field(
        default=5,
        description="Интервал в секундах между принудительными обновлениями ключей",
    )

    clock_skew: float = Field(
        default=5.0,
        ge=0,
        le=60,
        description=(
            "Допустимая погрешность часов сервера в секундах при проверке времени жизни токена"
        ),
    )
    timeout: PositiveFloat = Field(
        default=10.0,
        description="Таймаут в секундах на сетевые запросы к Keycloak",
    )
    pool_limit: PositiveInt = Field(
        default=20,
        description="Максимальное количество соединений в пуле",
    )

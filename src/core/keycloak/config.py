from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_")

    issuer_url: str = Field(
        default="http://localhost:8081/realms/tiu-media-hub",
        description="Публичный URL который видит frontend."
    )
    jwks_url: str = Field(
        default="http://keycloak:8080/realms/tiu-media-hub/protocol/openid-connect/certs",
        description="URL доступный для backend сервера.",
    )
    audience: str = "tiu-media-hub-api"
    algorithms: tuple[str, ...] = ("RS256",)
    jwks_cache_ttl: int = 300

    timeout: float = 30 * 10

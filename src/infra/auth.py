"""
Аутентификация: DDF проверяет подпись и claims токена Keycloak, здесь claims превращаются в ``Auth``.
Keycloak отвечает только за личность и глобальную роль ``admin``; права на коллекции — в нашей БД.
"""

from typing import Any

from uuid import UUID

from ddf.infra.integrations.keycloak import KeycloakConfig, KeycloakTokenVerifier, VerifiedToken
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.auth import Auth, AuthType, AuthUser, UnauthorizedError


class ClientsConfig(BaseSettings):
    """Разрешённые клиенты Keycloak (``azp``): разделяют пользователей и сервисы."""

    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_")

    user_client_ids: frozenset[str] = Field(default=frozenset({"tiu-media-hub-web", "tiu-media-hub-dev"}))
    service_client_ids: frozenset[str] = Field(default=frozenset({"tiu-media-hub-service"}))


def resolve_auth(token: VerifiedToken, *, audience: str, clients: ClientsConfig) -> Auth:
    claims: Any = token.claims
    client_id = claims.get("azp")
    roles = frozenset(claims.get("resource_access", {}).get(audience, {}).get("roles", []))

    if client_id in clients.service_client_ids:
        return Auth(id=client_id, type=AuthType.SERVICE, roles=roles)

    if client_id not in clients.user_client_ids:
        raise UnauthorizedError("Unknown client.")

    try:
        user_id = UUID(token.subject)
    except ValueError:
        raise UnauthorizedError("Invalid subject.") from None

    return AuthUser(
        id=token.subject,
        type=AuthType.USER,
        roles=roles,
        user=Auth.User(
            id=user_id,
            username=claims.get("preferred_username"),
            email=claims.get("email"),
            full_name=claims.get("name"),
        ),
    )


class KeycloakAuthenticator:
    def __init__(self, config: KeycloakConfig, clients: ClientsConfig) -> None:
        self._verifier = KeycloakTokenVerifier(config)
        self._audience = config.audience
        self._clients = clients

    async def authenticate(self, token: str) -> Auth:
        verified = await self._verifier.verify(token)
        return resolve_auth(verified, audience=self._audience, clients=self._clients)

    async def close(self) -> None:
        await self._verifier.close()


__all__ = ["ClientsConfig", "KeycloakAuthenticator", "resolve_auth"]

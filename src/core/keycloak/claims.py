from typing import Any

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.models import Auth, Client, User

from .config import KeycloakConfig


class _TokenClaims(BaseModel):
    """Полезная нагрузка полученная из JWT токена Keycloak."""

    model_config = ConfigDict(strict=True)

    class _ResourceAccess(BaseModel):
        roles: list[str] = Field(default_factory=list)

    sub: str = Field(min_length=1)
    azp: str = Field(min_length=1)
    resource_access: dict[str, _ResourceAccess] = Field(default_factory=dict)

    preferred_username: str | None = Field(default=None, description="Никнейм пользователя")
    email: EmailStr | None = Field(default=None, description="Электронная почта пользователя")
    email_verified: bool = Field(default=False, description="Подтверждена ли почта")
    name: str | None = Field(default=None, description="Полное имя пользователя")


def _get_roles(claims: _TokenClaims, audience: str) -> frozenset[str]:
    """Безопасно извлекает роли для указанной аудитории."""

    access = claims.resource_access.get(audience)
    return frozenset(access.roles) if access else frozenset()


def build_auth_from_claims(payload: Mapping[str, Any], config: KeycloakConfig) -> Auth:
    try:
        claims = _TokenClaims.model_validate(payload)
    except ValidationError as exc:
        raise AuthenticationError("Invalid access token claims") from exc

    roles = _get_roles(claims, config.audience)
    client_id = claims.azp

    if claims.azp in config.service_client_ids:
        return Client(client_id=client_id, roles=roles)

    if client_id in config.user_client_ids:
        try:
            user_id = UUID(claims.sub)
        except ValueError:
            raise AuthenticationError("User subject must be valid UUID.") from None

        return User(
            id=user_id,
            username=claims.preferred_username,
            email=claims.email,
            full_name=claims.name,
            roles=roles,
        )

    raise AuthenticationError("Untrusted client application (azp).")

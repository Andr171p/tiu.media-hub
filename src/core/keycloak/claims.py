from typing import Any, Literal

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError

from src.core.auth import Auth, AuthClient, AuthType, AuthUser, UnauthorizedError

from .config import KeycloakConfig


class _ResourceAccess(BaseModel):
    roles: list[str] = Field(default_factory=list)


class _TokenClaims(BaseModel):
    """Проверенная полезная нагрузка access-токена Keycloak."""

    model_config = ConfigDict(strict=True)

    sub: UUID
    azp: str = Field(min_length=1)
    typ: Literal["Bearer"]
    resource_access: dict[str, _ResourceAccess] = Field(default_factory=dict)

    preferred_username: str | None = None
    email: EmailStr | None = None
    email_verified: bool = False
    name: str | None = None


def build_auth_from_claims(payload: Mapping[str, Any], config: KeycloakConfig) -> AuthUser | AuthClient:
    """
    Тип субъекта определяется клиентом, выпустившим токен (``azp``), по непересекающимся allowlist.
    Учитываются только роли клиента API: realm-роли и роли других клиентов игнорируются.
    """

    try:
        claims = _TokenClaims.model_validate(payload, strict=False)
    except ValidationError as exc:
        raise UnauthorizedError("Invalid access token claims.") from exc

    access = claims.resource_access.get(config.audience)
    roles = frozenset(access.roles) if access else frozenset()

    if claims.azp in config.service_client_ids:
        return AuthClient(
            id=claims.sub,
            type=AuthType.CLIENT,
            client=Auth.Client(id=claims.azp, roles=roles),
        )

    if claims.azp in config.user_client_ids:
        return AuthUser(
            id=claims.sub,
            type=AuthType.USER,
            user=Auth.User(
                id=claims.sub,
                email=claims.email,
                email_verified=claims.email_verified,
                username=claims.preferred_username,
                full_name=claims.name,
                roles=roles,
            ),
        )

    raise UnauthorizedError("Untrusted client application.")


__all__ = ["build_auth_from_claims"]

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth import (
    ASSETS_READ_ROLE,
    Auth,
    AuthClient,
    AuthType,
    AuthUser,
    PermissionDeniedError,
    UnauthorizedError,
)
from src.core.keycloak import KeycloakClient

bearer_scheme = HTTPBearer(auto_error=False, description="Access-токен Keycloak")


async def get_current_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Auth:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing or invalid credentials.")

    keycloak: KeycloakClient = request.app.state.keycloak_client
    return await keycloak.verify_token(credentials.credentials)


CurrentAuth = Annotated[Auth, Depends(get_current_auth)]


def get_current_user(auth: CurrentAuth) -> AuthUser:
    if auth.type is not AuthType.USER or auth.user is None:
        raise PermissionDeniedError("User authentication required.")

    return AuthUser.model_validate(auth, from_attributes=True)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def get_current_admin(user: CurrentUser) -> AuthUser:
    if not user.is_admin:
        raise PermissionDeniedError("Administrator role required.")

    return user


CurrentAdmin = Annotated[AuthUser, Depends(get_current_admin)]


def get_current_client(auth: CurrentAuth) -> AuthClient:
    """Доверенный сервис (Client Credentials) с правом чтения DAM."""

    if auth.type is not AuthType.CLIENT or auth.client is None:
        raise PermissionDeniedError("Client authentication required.")

    client = AuthClient.model_validate(auth, from_attributes=True)
    if not client.has_role(ASSETS_READ_ROLE):
        raise PermissionDeniedError(f"Client role {ASSETS_READ_ROLE!r} required.")

    return client


CurrentClient = Annotated[AuthClient, Depends(get_current_client)]

__all__ = ["CurrentAdmin", "CurrentAuth", "CurrentClient", "CurrentUser"]

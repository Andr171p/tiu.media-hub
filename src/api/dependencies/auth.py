from typing import Annotated

from ddf.infra.cache import InMemoryCache
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.auth import (
    SERVICE_READ_ROLE,
    Auth,
    AuthType,
    AuthUser,
    PermissionDeniedError,
    UnauthorizedError,
)
from src.application.users import sync_profile
from src.infra.auth import KeycloakAuthenticator
from src.infra.database.repositories import SqlAlchemyUserRepository

_PROFILE_SYNC_TTL = 15 * 60

bearer_scheme = HTTPBearer(auto_error=False, description="Access token Keycloak")


async def _sync_profile(request: Request, auth: AuthUser) -> None:
    """Профиль из токена сохраняется не чаще раза в 15 минут на процесс."""

    cache: InMemoryCache[bool] = request.app.state.profile_cache
    key = f"profile:{auth.user.model_dump_json()}"

    if await cache.get(key):
        return

    async with request.app.state.session_factory() as session:
        await sync_profile(auth, user_repository=SqlAlchemyUserRepository(session), uow=session)

    await cache.set(key, True, ttl=_PROFILE_SYNC_TTL)


async def get_optional_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Auth | None:
    if credentials is None or not credentials.credentials:
        return None

    authenticator: KeycloakAuthenticator = request.app.state.authenticator
    auth = await authenticator.authenticate(credentials.credentials)

    if isinstance(auth, AuthUser):
        await _sync_profile(request, auth)

    return auth


OptionalAuth = Annotated[Auth | None, Depends(get_optional_auth)]


def get_current_auth(auth: OptionalAuth) -> Auth:
    if auth is None:
        raise UnauthorizedError("Missing credentials.")
    return auth


CurrentAuth = Annotated[Auth, Depends(get_current_auth)]


def get_current_user(auth: CurrentAuth) -> AuthUser:
    if not isinstance(auth, AuthUser):
        raise PermissionDeniedError("User authentication required.")
    return auth


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def get_current_service(auth: CurrentAuth) -> Auth:
    if auth.type is not AuthType.SERVICE or SERVICE_READ_ROLE not in auth.roles:
        raise PermissionDeniedError(f"Service with role {SERVICE_READ_ROLE!r} required.")
    return auth


CurrentService = Annotated[Auth, Depends(get_current_service)]

__all__ = ["CurrentAuth", "CurrentService", "CurrentUser", "OptionalAuth"]

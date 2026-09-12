from typing import Annotated

from collections.abc import Callable

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.models import Auth, Client, User
from src.modules.keycloak import KeycloakError, keycloak_client

http_bearer = HTTPBearer(auto_error=False, description="Keycloak access token (Bearer).")


async def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> Auth:
    """Зависимость для валидации токена и получения текущего аутентифицированного субъекта."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await keycloak_client.verify_token(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc

    except KeycloakError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
            headers={"Retry-After": "5"},
        ) from exc


CurrentAuth = Annotated[Auth, Depends(get_current_auth)]


def require_auth[T: Client | User](expected_type: type[T]) -> Callable[[Auth], T]:
    """Зависимость требующая определённый тип субъекта."""

    def dependency(auth: CurrentAuth) -> T:
        if not isinstance(auth, expected_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{expected_type.__name__.lower().capitalize()} authentication required."
            )

        return auth
    return dependency


CurrentUser = Annotated[User, Depends(require_auth(User))]
CurrentClient = Annotated[Client, Depends(require_auth(Client))]

auth_security = Security(get_current_auth)
auth_user_security = Security(require_auth(User))
auth_client_security = Security(require_auth(Client))


def require_roles(*roles: str, all_required: bool = False) -> Callable[..., Auth]:
    """Зависимость для проверки ролей текущего субъекта авторизации."""

    required = frozenset(roles)

    if not required:
        raise ValueError("At least one required role must be specified.")

    def dependency(auth: CurrentAuth) -> Auth:
        allowed = required <= auth.roles if all_required else not required.isdisjoint(auth.roles)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return auth
    return dependency

from typing import Annotated

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth.models import User
from src.modules.keycloak import keycloak_client

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> User:
    """Получает текущего аутентифицированного пользователя."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await keycloak_client.verify_token(credentials.credentials)


def require_roles(*roles: str) -> Callable[[User], User]:
    """Требует чтобы хотя бы одна роль была у текущего пользователя."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not set(roles).isdisjoint(user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.",
            )

        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.models import User
from src.services.keycloak import keycloak_client

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> User:

    if credentials is None:
        raise AuthenticationError("Authentication required")

    return await keycloak_client.verify_token(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]

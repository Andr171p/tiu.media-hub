import asyncio

import aiohttp

from .config import KeycloakConfig


class KeycloakUsersClient:
    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        self._token_lock = asyncio.Lock()

    async def _get_token_session(self): ...

    async def get_users(self, search: str, *, limit: int = 50, offset: int = 0): ...

    async def get_user(self, user_id: str): ...

    async def is_user_exists(self, user_id: str) -> bool: ...

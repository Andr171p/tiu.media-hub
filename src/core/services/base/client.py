import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from fastapi import status
from pydantic import BaseModel

from src.core.services.base.config import SrvBaseConfig
from src.core.services.base.exceptions import OAuthError


class _OAuthToken(BaseModel):
    access_token: str
    expires_at: float


class SrvBaseClient:
    def __init__(self, config: SrvBaseConfig) -> None:
        self._config = config

        self._session: aiohttp.ClientSession | None = None
        self._token_state: _OAuthToken | None = None
        self._token_lock = asyncio.Lock()

    @asynccontextmanager
    async def _get_token_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        """Возвращает HTTP-сессию с актуальным OAuth access token."""

        async with self.__get_session() as session:
            access_token = await self.__get_access_token()
            session.headers["Authorization"] = f"Bearer {access_token}"
            yield session

    @asynccontextmanager
    async def __get_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            connector = aiohttp.TCPConnector(
                limit=self._config.pool_limit,
                ttl_dns_cache=300,
                keepalive_timeout=self._config.keepalive_timeout,
            )
            self._session = aiohttp.ClientSession(
                base_url=str(self._config.base_url).rstrip("/"),
                timeout=timeout,
                connector=connector,
            )

        yield self._session

    async def __request_oauth_token(self) -> _OAuthToken:

        credentials = {
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }

        timeout = aiohttp.ClientTimeout(total=self._config.timeout)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(self._config.token_url, data=credentials) as response,
        ):
            data = await response.json()
            if response.status != status.HTTP_200_OK:
                error_code = data.get("error_code") or "UNKNOWN_ERROR"
                error_msg = data.get("message", "")
                raise OAuthError(
                    f"[OAuth] Failed to fetch token. HTTP status: {response.status}. "
                    f"Error code: '{error_code}'. Message: {error_msg}"
                )

            data = await response.json()
            return _OAuthToken.model_validate(data)

    def __is_token_expired(self) -> bool:
        """Проверяет, требуется ли обновить сохранённый access token."""

        if self._token_state is None:
            return False

        return time.monotonic() >= self._token_state.expires_at - self._config.token_rotate_margin

    async def __get_access_token(self) -> str:
        """Возвращает кешированный токен или получает новый при необходимости."""

        if not self.__is_token_expired():
            return self._token_state.access_token

        async with self._token_lock:
            if not self.__is_token_expired():
                return self._token_state.access_token

            self._token_state = await self.__request_oauth_token()

        return self._token_state.access_token

    async def close(self) -> None:
        if self._session is None:
            return

        await self._session.close()
        self._session = None
        self._token_state = None

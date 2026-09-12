from typing import Literal, NamedTuple

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

import aiohttp
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    SecretStr,
)

from .config import SrvBaseConfig
from .exceptions import OAuthError


class _TokenResponse(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    access_token: SecretStr = Field(min_length=1, description="")
    expires_in: PositiveInt = Field(description="")
    token_type: Literal["Bearer"]


class _TokenState(NamedTuple):
    access_token: SecretStr
    refresh_at: float


class SrvBaseClient:
    def __init__(self, config: SrvBaseConfig) -> None:
        self._config = config

        self._session: aiohttp.ClientSession | None = None

        self._token_state: _TokenState | None = None
        self._token_lock = asyncio.Lock()

    @asynccontextmanager
    async def _get_token_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        token = await self.__get_access_token()

        session = self.__get_session()
        session.headers["Authorization"] = f"Bearer {token.access_token.get_secret_value()}"

        yield session

    def __get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            connector = aiohttp.TCPConnector(
                limit=self._config.pool_limit,
                keepalive_timeout=self._config.keepalive_timeout,
                ssl=self._config.verify_ssl,
            )
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        return self._session

    async def __load_access_token(self) -> _TokenState:
        """Получает access токен от сервера авторизации (OAuth flow)."""

        payload = {
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret.get_secret_value(),
        }

        if self._config.scope:
            payload["scope"] = self._config.scope

        requested_at = time.monotonic()

        session = self.__get_session()
        async with session.post(
            url=str(self._config.token_url),
            data=payload,
            allow_redirects=False,
        ) as response:
            if response.status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
                raise OAuthError(
                    f"[OAuth] ({response.status}) Token endpoint rejected credentials.",
                )

            data = await response.json()

        token = _TokenResponse.model_validate(data)

        rotate_margin = min(self._config.token_rotate_margin, token.expires_in / 2)
        refresh_at = requested_at + token.expires_in - rotate_margin

        if refresh_at <= time.monotonic():
            raise OAuthError("Token was already due for renewal when received.")

        return _TokenState(token.access_token, refresh_at)

    async def __get_access_token(self) -> _TokenState:
        """Потоко-безопасное получение access токена."""

        now = time.monotonic()

        if self._token_state is not None and now < self._token_state.refresh_at:
            return self._token_state

        async with self._token_lock:
            if self._token_state is None or now >= self._token_state.refresh_at:
                self._token_state = await self.__load_access_token()

            return self._token_state

    async def close(self) -> None:
        """Безопасное закрытие соединения и сброс состояния."""

        if self._session is not None:
            await self._session.close()
            self._session = None

        self._token_state = None

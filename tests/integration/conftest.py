"""
Интеграционные тесты против запущенного стека (``docker compose up -d``).
Токены выдаёт Keycloak через dev-клиент с password grant (только для разработки).
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest

API_URL = os.getenv("TEST_API_URL", "http://localhost:8000/api/v1")
TOKEN_URL = os.getenv(
    "TEST_TOKEN_URL", "http://localhost:8081/realms/tiu-media-hub/protocol/openid-connect/token"
)

type Login = Callable[[str], Awaitable[httpx.AsyncClient]]

# Локальный системный прокси Windows ломает запросы к localhost
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")


async def _token(username: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": "tiu-media-hub-dev",
                "username": username,
                "password": username,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]


@pytest.fixture
async def login() -> AsyncIterator[Login]:
    """Клиент API от имени пользователя (пароль dev-пользователей совпадает с логином)."""

    clients: list[httpx.AsyncClient] = []

    async def _login(username: str) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            base_url=API_URL, headers={"Authorization": f"Bearer {await _token(username)}"}, timeout=60
        )
        clients.append(client)
        return client

    yield _login

    for client in clients:
        await client.aclose()

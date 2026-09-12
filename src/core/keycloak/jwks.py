import asyncio
import time
from collections.abc import Collection
from http import HTTPStatus

import aiohttp
import jwt

from .config import KeycloakConfig
from .exceptions import KeycloakError

_NEGATIVE_INF = float("-inf")


def _parse_jwk(raw_key: object, allowed_algorithms: Collection[str]) -> jwt.PyJWK | None:
    """Валидирует и парсит один JWK. Возвращает PyJWK или None, если ключ не подходит."""

    if not isinstance(raw_key, dict):
        return None

    if not isinstance((kid := raw_key.get("kid")), str) or not kid:
        return None

    if raw_key.get("use") not in {None, "sig"}:
        return None

    key_ops = raw_key.get("key_ops")
    if key_ops is not None and (not isinstance(key_ops, list) or "verify" not in key_ops):
        return None

    if (algorithm := raw_key.get("alg")) is not None and algorithm not in allowed_algorithms:
        return None

    key = jwt.PyJWK.from_dict(raw_key)
    if key.algorithm_name in allowed_algorithms:
        return key

    return None


def _parse_jwks(document: object, allowed_algorithms: Collection[str]) -> dict[str, jwt.PyJWK]:
    """Парсит поддерживаемые подписанные ключи из JWKS документа."""

    if not isinstance(document, dict):
        raise TypeError("JWKS must be an valid dict.")

    raw_keys = document.get("keys")
    if not isinstance(raw_keys, list):
        raise TypeError("JWKS does not contain a valid 'keys' array.")

    keys: dict[str, jwt.PyJWK] = {}

    for raw_key in raw_keys:
        if (key := _parse_jwk(raw_key, allowed_algorithms)) is None:
            continue

        kid = key.key_id
        if kid in keys:
            raise ValueError(f"Duplicate signing key ID: {kid!r}.")

        keys[kid] = key

    if not keys:
        raise ValueError("JWKS contains no supported signing keys.")

    return keys


class KeycloakJwksClient:
    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config

        self._session: aiohttp.ClientSession | None = None

        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded_at = _NEGATIVE_INF

        self._retry_after = _NEGATIVE_INF
        self._unknown_kid_refresh_after = _NEGATIVE_INF

        self._refresh_lock = asyncio.Lock()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._config.timeout)
            connector = aiohttp.TCPConnector(limit=self._config.pool_limit)
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        return self._session

    def _is_fresh(self, now: float) -> bool:
        return bool(self._keys) and now - self._loaded_at < self._config.jwks_cache_ttl

    async def _load_keys(self) -> dict[str, jwt.PyJWK]:
        """"""

        session = self._get_session()
        async with session.get(str(self._config.jwks_url), allow_redirects=False) as response:
            if response.status != HTTPStatus.OK:
                raise KeycloakError("[Keycloak] Signing keys are unavailable.")

            doc = await response.json()

        return _parse_jwks(doc, self._config.algorithms)

    async def get_key(self, kid: str) -> jwt.PyJWK:
        now = time.monotonic()

        if self._is_fresh(now) and (key := self._keys.get(kid)) is not None:
            return key

        async with self._refresh_lock:
            now = time.monotonic()

            if self._is_fresh(now) and (key := self._keys.get(kid)) is not None:
                return key

            if now < self._retry_after:
                raise KeycloakError("[Keycloak] Signing keys are temporarily unavailable.")

            # Не позволяет случайным kid постоянно обращаться в keycloak
            if self._is_fresh(now) and now < self._unknown_kid_refresh_after:
                raise KeycloakError("[Keycloak] Unknown signing key.")

            try:
                keys = await self._load_keys()
            except Exception:
                self._retry_after = time.monotonic() + self._config.jwks_refresh_cooldown
                raise

            now = time.monotonic()
            self._keys = keys
            self._loaded_at = now

            if (key := keys.get(kid)) is None:
                self._unknown_kid_refresh_after = now + self._config.jwks_refresh_cooldown
                raise KeycloakError("[Keycloak] Unknown signing key.")

        return key

    async def close(self) -> None:
        """Безопасное закрытие сессии и инвалидация кеша."""

        if self._session is not None:
            await self._session.close()
            self._session = None

        self._keys.clear()

        self._loaded_at = _NEGATIVE_INF
        self._retry_after = _NEGATIVE_INF
        self._unknown_kid_refresh_after = _NEGATIVE_INF

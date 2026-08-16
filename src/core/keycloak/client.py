from typing import Any

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from uuid import UUID

import aiohttp
import jwt
from jwt.algorithms import RSAAlgorithm, RSAPublicKey
from jwt.exceptions import InvalidTokenError

from src.core.auth.exceptions import AuthenticationError
from src.core.auth.models import User

from .config import KeycloakConfig

_JWT_OPTIONS: tuple[str, ...] = ("exp", "iat", "iss", "sub")


def _build_user_from_claims(claims: Mapping[str, Any]) -> User:

    if (sub := claims.get("sub")) is None:
        raise AuthenticationError("Missing required 'sub' claim.")

    try:
        user_id = UUID(sub)
    except (ValueError, TypeError):
        raise AuthenticationError("Invalid 'sub' claim.") from None

    realm_access = claims.get("realm_access", {})
    roles = frozenset(realm_access.get("roles", ()))

    username, email = claims.get("preferred_username"), claims.get("email")

    return User(
        id=user_id,
        username=username,
        email=email,
        roles=roles,
    )


class KeycloakClient:
    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None

        self._keys: dict[str, RSAPublicKey] = {}
        self._keys_loaded_at: int = 0.0
        self._keys_lock = asyncio.Lock()

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        timeout = aiohttp.ClientTimeout(total=self._config.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            yield session

    async def _load_keys(self, *, force: bool = False) -> None:
        """Загружает подписанные ключи из Keycloak."""

        now = time.monotonic()

        if (
            not force
            and self._keys
            and now - self._keys_loaded_at < self._config.jwks_cache_ttl
        ):
            return

        async with self._keys_lock:

            async with (
                self._get_session() as session,
                session.get(self._config.jwks_url) as response,
            ):
                response.raise_for_status()
                data = await response.json()

            self._keys = {
                kid: RSAAlgorithm.from_jwk(key)
                for key in data.get("keys", [])
                if (kid := key.get("kid")) is not None
            }
            self._keys_loaded_at = time.monotonic()

    async def _get_key(self, kid: str) -> RSAAlgorithm:

        if kid not in self._keys:
            await self._load_keys()

        if (key := self._keys.get(kid)) is None:
            raise AuthenticationError("Unknown signing key.")

        return key

    async def verify_token(self, token: str) -> User:

        try:
            header = jwt.get_unverified_header(token)

            if not (kid := header.get("kid")):
                raise AuthenticationError("Token does not contain kid.")

            key = await self._get_key(kid)

            payload = jwt.decode(
                token,
                key=key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer_url,
                options={"require": list(_JWT_OPTIONS)}
            )
        except InvalidTokenError as exc:
            raise AuthenticationError("Invalid access token.") from exc
        else:
            return _build_user_from_claims(payload)

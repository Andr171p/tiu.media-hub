"""Пароли порталов (scrypt) и токены посетителей (HMAC): без внешних зависимостей."""

import base64
import hashlib
import hmac
import secrets
import time
from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.application.portals.ports import PortalSecrets

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class PortalSecretsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PORTAL_")

    secret: SecretStr = SecretStr("dev-portal-secret")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class HmacPortalSecrets(PortalSecrets):
    def __init__(self, config: PortalSecretsConfig) -> None:
        self._key = config.secret.get_secret_value().encode()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
        return f"scrypt${_b64(salt)}${_b64(digest)}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            _, salt, expected = password_hash.split("$")
            digest = hashlib.scrypt(password.encode(), salt=_unb64(salt), **_SCRYPT)
        except ValueError:
            return False

        return hmac.compare_digest(digest, _unb64(expected))

    def _sign(self, payload: str) -> str:
        return _b64(hmac.new(self._key, payload.encode(), hashlib.sha256).digest())

    def issue_token(self, portal_id: UUID, *, ttl: int) -> str:
        payload = f"{portal_id}.{int(time.time()) + ttl}"
        return f"{payload}.{self._sign(payload)}"

    def verify_token(self, token: str, portal_id: UUID) -> bool:
        try:
            token_portal, expires, signature = token.split(".")
            payload = f"{token_portal}.{expires}"
            return (
                token_portal == str(portal_id)
                and int(expires) > time.time()
                and hmac.compare_digest(signature, self._sign(payload))
            )
        except ValueError:
            return False


__all__ = ["HmacPortalSecrets", "PortalSecretsConfig"]

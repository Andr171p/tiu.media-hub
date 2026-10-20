import base64
import hashlib
import time

from src.application.storage import MediaUrls

from .config import CdnConfig


class SignedCdnUrls(MediaUrls):
    """
    Ссылки nginx ``secure_link``: ``md5(expires + uri + " " + secret)``.

    Срок округляется до окна ``url_ttl``: в пределах окна ссылка одинакова, поэтому браузер
    берёт файл из кеша, а живёт ссылка от одного до двух окон.
    """

    def __init__(self, config: CdnConfig) -> None:
        self._base_url = str(config.base_url).rstrip("/")
        self._secret = config.secret.get_secret_value()
        self._ttl = config.url_ttl

    def url(self, key: str) -> str:
        expires = (int(time.time()) // self._ttl + 2) * self._ttl
        uri = f"/media/{key}"
        digest = hashlib.md5(f"{expires}{uri} {self._secret}".encode(), usedforsecurity=False).digest()
        token = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return f"{self._base_url}{uri}?expires={expires}&token={token}"


__all__ = ["SignedCdnUrls"]

import base64
import hashlib
import time
from urllib.parse import quote, urlencode

from .config import CdnConfig


class CdnClient:
    """
    Подписанные ссылки на объекты через nginx (модуль ``secure_link``).

    Бакет закрыт: читать его может только CDN, а CDN отдаёт объект лишь по ссылке
    с действующей подписью. Сам объект неизменяем, поэтому nginx кеширует его по пути без подписи.
    """

    def __init__(self, config: CdnConfig) -> None:
        self._config = config
        self._prefix = "/" + config.path_prefix.strip("/")
        self._secret = config.secret.get_secret_value()

    def _expires_at(self, now: float) -> int:
        # Не меньше одного полного окна в запасе
        window = self._config.link_ttl
        return (int(now) // window + 2) * window

    def url(self, storage_key: str, *, now: float | None = None) -> str:
        path = f"{self._prefix}/{quote(storage_key, safe='/')}"
        expires = self._expires_at(time.time() if now is None else now)

        # Совпадает с nginx: secure_link_md5 "$secure_link_expires$uri <secret>"
        digest = hashlib.md5(f"{expires}{path} {self._secret}".encode(), usedforsecurity=False).digest()
        token = base64.urlsafe_b64encode(digest).decode().rstrip("=")

        return f"{self._config.base_url.rstrip('/')}{path}?{urlencode({'token': token, 'expires': expires})}"


__all__ = ["CdnClient"]

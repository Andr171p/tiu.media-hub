from urllib.parse import quote

from .config import CdnConfig


class CdnClient:
    def __init__(self, config: CdnConfig) -> None:
        self._config = config

    def url(self, path: str) -> str:
        """"""

        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        prefix = self._config.path_prefix.lstrip("/")
        return f"{self._config.base_url}/{prefix}/{encoded_path}"

"""Порты файлового хранилища. Оригиналы и производные лежат в разных бакетах: производные раздаёт CDN."""

from typing import Protocol

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UploadedPart:
    number: int
    etag: str


class FileStorage(Protocol):
    async def create_upload_url(self, key: str, content_type: str, *, expires_in: int) -> str: ...

    async def start_multipart_upload(self, key: str, content_type: str) -> str:
        """Возвращает идентификатор multipart-загрузки."""

    async def create_part_upload_urls(
        self, key: str, multipart_id: str, *, parts: int, expires_in: int
    ) -> list[str]: ...

    async def complete_multipart_upload(
        self, key: str, multipart_id: str, parts: Sequence[UploadedPart]
    ) -> None: ...

    async def abort_multipart_upload(self, key: str, multipart_id: str) -> None: ...

    async def get_size(self, key: str) -> int | None:
        """Размер объекта или ``None``, если объекта нет."""

    async def create_download_url(self, key: str, *, filename: str, expires_in: int) -> str: ...

    async def download_file(self, key: str, path: Path) -> None: ...

    async def download_bytes(self, key: str) -> bytes:
        """Для небольших файлов (превью)."""

    async def upload_file(self, key: str, path: Path, content_type: str) -> None: ...

    async def upload_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    async def delete_many(self, keys: Sequence[str]) -> None: ...


class MediaUrls(Protocol):
    def url(self, key: str) -> str:
        """Временная ссылка CDN на производную (превью, прокси)."""


__all__ = ["FileStorage", "MediaUrls", "UploadedPart"]

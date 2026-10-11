from __future__ import annotations

from typing import IO

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from src.core.s3 import S3Client, S3NotFoundError

from .models import StoredObject


@dataclass(frozen=True, slots=True)
class Digest:
    sha256: str
    size: int

    @classmethod
    def of(cls, obj: StoredObject) -> Digest:
        """Подтверждённый при загрузке отпечаток объекта."""

        return cls(sha256=obj.sha256, size=obj.size_bytes)


async def stream_object(s3: S3Client, key: str, sink: IO[bytes] | None = None) -> Digest:
    """Читает объект целиком, считая SHA-256; при необходимости копирует содержимое в ``sink``."""

    hasher = hashlib.sha256()
    size = 0

    async for chunk in s3.iter_chunks(key):
        hasher.update(chunk)
        size += len(chunk)
        if sink is not None:
            sink.write(chunk)

    return Digest(sha256=hasher.hexdigest(), size=size)


def describe_mismatch(expected: Digest, actual: Digest) -> str | None:
    if actual.size != expected.size:
        return f"Size mismatch: expected {expected.size}, got {actual.size}."
    if actual.sha256 != expected.sha256:
        return "SHA-256 mismatch: content differs from the verified original."
    return None


async def verify_object(s3: S3Client, obj: StoredObject) -> bool:
    """Проверка фиксированности (fixity): содержимое в хранилище совпадает с подтверждённым при загрузке."""

    try:
        error = describe_mismatch(Digest.of(obj), await stream_object(s3, obj.storage_key))
    except S3NotFoundError:
        error = "Object is missing in storage."

    obj.integrity_error = error
    if error is None:
        obj.verified_at = datetime.now(UTC)

    return error is None


__all__ = ["Digest", "describe_mismatch", "stream_object", "verify_object"]

from typing import Annotated

from pydantic import Field

_SHA256_LENGTH = 64

type FilePathStr = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r'^[^\\/:*?"<>|]+$',
        description="Корректное имя файла без запрещенных символов",
        examples=["image.jpg"]
    ),
]

type Sha256Str = Annotated[
    str,
    Field(
        min_length=_SHA256_LENGTH,
        max_length=_SHA256_LENGTH,
        pattern=r"^[a-fA-F0-9]{64}$",
        description="Sha256 хеш (строка)"
    ),
]

__all__ = ["FilePathStr", "Sha256Str"]

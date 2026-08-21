from typing import Annotated

from pydantic import Field, NonNegativeInt

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

type FileSize = Annotated[
    NonNegativeInt, Field(description="Размер файла в байтах.", examples=[5242880]),
]

type MimeType = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        description="Mime тип файла.",
        examples=["image/png", "audio/mpeg"]
    ),
]

__all__ = ["FilePathStr", "FileSize", "MimeType"]

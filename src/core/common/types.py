from typing import Annotated

from pydantic import Field, StringConstraints

type Str255 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

type Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]

type Sha256Hex = Annotated[
    str,
    StringConstraints(to_lower=True, pattern=r"^[a-fA-F0-9]{64}$"),
    Field(
        description="SHA-256 в hex",
        examples=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    ),
]

type FileName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=255, pattern=r'^[^\/:*?"<>|\x00-\x1f]+$'
    ),
    Field(description="Имя файла без пути и запрещённых символов", examples=["photo.jpg"]),
]

type MimeType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[\w.+-]+/[\w.+-]+$", max_length=255),
    Field(description="MIME-тип", examples=["image/jpeg"]),
]

__all__ = ["Description", "FileName", "MimeType", "Sha256Hex", "Str255"]

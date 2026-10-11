from typing import Literal

from uuid import UUID

from pydantic import Field, PositiveInt

from src.core.common.schemas import Schema
from src.core.common.types import FileName, MimeType, Sha256Hex


class CreateUploadDTO(Schema):
    filename: FileName
    content_type: MimeType = Field(description="MIME-тип, с которым файл будет загружен")
    size_bytes: PositiveInt = Field(description="Размер файла, байт")
    sha256: Sha256Hex = Field(description="SHA-256 содержимого: хранилище проверит его при загрузке")


class UploadTarget(Schema):
    url: str = Field(description="Presigned URL для прямой загрузки")
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str] = Field(description="Заголовки, которые нужно отправить с файлом")
    expires_in: PositiveInt = Field(description="Срок действия ссылки, секунд")


class UploadResponse(Schema):
    """
    Файл загружается всегда, даже если такое содержимое уже хранится: знание хеша
    не должно давать доступ к чужому файлу. Дубликаты сливаются после проверки.
    """

    id: UUID = Field(description="Идентификатор сессии загрузки")
    target: UploadTarget


class StoredObjectResponse(Schema):
    id: UUID
    size_bytes: int
    sha256: str
    content_type: str

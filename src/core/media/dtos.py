from typing import Literal

from collections.abc import Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveInt
from pydantic.alias_generators import to_camel

from .types import FilePathStr, Sha256Str


class CreateUploadDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    filename: FilePathStr
    content_type: str | None = Field(
        default=None,
        description="MIME-тип загружаемого файла",
        examples=["image/png", "plain/text"],
    )
    size_bytes: PositiveInt = Field(description="Размер файла в байтах")
    sha256: Sha256Str


class UploadInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    url: HttpUrl = Field(description="Временный URL для прямой загрузки")
    method: Literal["PUT"] = "PUT"
    headers: Mapping[str, str] = Field(default_factory=dict, description="Необходимые заголовки")
    expires_in: PositiveInt = Field(description="Время действия в секундах")


class UploadResponse(BaseModel):
    id: UUID = Field(description="Идентификатор сессии загрузки")
    upload: UploadInfo = Field(description="Информация для прямой загрузки файла в S3")


class StoredObjectResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID = Field(description="Уникальный идентификатор сохранённого объекта")
    url: HttpUrl = Field(description="Ссылка на CDN")
    size_bytes: PositiveInt = Field(description="Размер объекта в байтах")
    content_type: str = Field(description="MIME-тип объекта")

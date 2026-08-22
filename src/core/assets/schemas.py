from typing import Literal

from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeInt,
)

from src.core.common.schemas import Str255

from .models import AssetStatus, AssetType
from .types import FilePathStr, FileSize, MimeType

# =================================================================================================
# Upload file DTOs
# =================================================================================================


class UploadAssetDTO(BaseModel):
    """DTO для загрузки файла."""

    filename: FilePathStr
    mime_type: MimeType
    size: FileSize


class UploadInfo(BaseModel):
    """Данные для прямой загрузки S3."""

    url: HttpUrl = Field(description="Временный URL для прямой загрузки.")
    method: Literal["PUT"] = Field(
        default="PUT",
        frozen=True,
        description="HTTP метод для загрузки в S3.",
    )
    expires_in: NonNegativeInt = Field(
        alias="expiresIn", description="Время жизни URL в секундах.",
    )


class UploadAssetResponse(BaseModel):
    """Результат инициации загрузки файла."""

    upload_id: UUID = Field(alias="uploadId", description="Идентификатор потока загрузки файла.")
    upload: UploadInfo = Field(description="Данные для прямой загрузки в S3.")


# =================================================================================================
# Asset CRUD DTOs
# =================================================================================================


class CreateAssetDTO(BaseModel):
    """DTO для создания записи медиа актива."""

    title: Str255 = Field(
        description="Название медиа-актива.", examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Описание и контекст медиа-актива.",
    )


class UpdateAssetDTO(BaseModel):
    """DTO для обновления медиа актива."""

    status: AssetStatus | None = Field(default=None, description="Новый статус.")
    current_version_id: UUID | None = Field(default=None, description="Актуальная версия актива.")


class AssetResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Уникальный идентификатор медиа актива.")
    created_at: AwareDatetime = Field(alias="createdAt", description="Дата создания.")
    updated_at: AwareDatetime = Field(alias="updatedAt", description="Дата последнего обновления.")

    title: Str255 = Field(description="Заголовок медиа актива.")
    description: str | None = Field(None, description="Описание и контекст медиа-актива.")
    type_: AssetType | None = Field(None, alias="type", description="Модальность актива.")
    status: AssetStatus = Field(description="Текущий статус.")

    author_id: UUID | None = Field(None, alias="authorId", description="Тот кто загрузил актив.")
    current_version_id: UUID | None = Field(None, description="Идентификатор актуальной версии.")

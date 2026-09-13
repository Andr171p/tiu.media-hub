from typing import Literal

from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
)
from pydantic.alias_generators import to_camel

from src.core.common.types import Str255

from .custom import CustomMeta
from .meta import AssetMeta
from .models import AssetStatus, VersionStatus
from .types import FilePathStr, FileSize, MimeType

# =================================================================================================
# Upload DTO
# =================================================================================================


class UploadAssetDTO(BaseModel):
    """Параметры загружаемого файла."""

    filename: FilePathStr
    mime_type: MimeType
    size: FileSize

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class UploadInfo(BaseModel):
    """Данные для прямой загрузки S3."""

    url: HttpUrl = Field(description="Временный URL для прямой загрузки")
    method: Literal["PUT"] = Field(
        default="PUT",
        frozen=True,
        description="HTTP метод для загрузки в S3",
    )
    expires_in: NonNegativeInt = Field(description="Время жизни URL в секундах")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class UploadResult(BaseModel):
    """Результат инициации загрузки файла."""

    upload_id: UUID = Field(description="Идентификатор потока загрузки файла")
    upload_info: UploadInfo = Field(description="Данные для прямой загрузки в S3")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

# =================================================================================================
# Object DTO
# =================================================================================================


class ObjectDTO(BaseModel):
    """Физический объект цифрового контента."""

    id: UUID = Field(description="Уникальный идентификатор объекта")
    url: HttpUrl = Field(description="Ссылка на CDN")
    mime_type: MimeType
    size: FileSize

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

# =================================================================================================
# Asset DTO
# =================================================================================================


class CreateAssetDTO(BaseModel):
    """DTO для создания записи медиа актива."""

    title: Str255 = Field(
        description="Название медиа-актива.",
        examples=["День открытых дверей 2026"],
    )
    description: str | None = Field(
        default=None,
        max_length=5000,
        description="Описание и контекст медиа-актива",
    )
    custom_meta: CustomMeta = Field(
        default_factory=dict,
        alias="customMeta",
        description="Пользовательские метаданные актива"
    )


class UpdateAssetDTO(BaseModel):
    """Обновление медиа актива."""

    status: AssetStatus | None = Field(default=None, description="Новый статус.")


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(description="Уникальный идентификатор медиа актива")
    created_at: AwareDatetime = Field(alias="createdAt", description="Дата создания")
    updated_at: AwareDatetime = Field(alias="updatedAt", description="Дата последнего обновления")

    title: Str255 = Field(description="Заголовок медиа актива")
    description: str | None = Field(default=None, description="Описание и контекст медиа-актива")
    custom_meta: CustomMeta = Field(
        default_factory=dict,
        description="Пользовательские метаданные актива",
    )

    status: AssetStatus = Field(description="Текущий статус")
    author_id: UUID | None = Field(
        default=None,
        alias="authorId",
        description="Тот кто загрузил актив",
    )

    current_version_id: UUID | None = Field(
        default=None,
        description="Идентификатор актуальной версии",
    )

# =================================================================================================
# Version DTO
# =================================================================================================


class CreateAssetVersionDTO(BaseModel):
    """Создание версии медиа актива."""

    mime_type: MimeType = Field(description="Фактический MIME-тип")
    size: FileSize = Field(description="Фактический размер объекта")
    checksum: str = Field(min_length=1, description="Контрольная сумма объекта")

    meta: AssetMeta | None = Field(
        default=None,
        description="Нормализованные технические метаданные",
    )
    raw_meta: dict[str, JsonValue] | None = Field(
        default=None,
        description="Исходные сырые метаданные",
    )

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class AssetVersionResponse(BaseModel):
    """Версия медиа актива."""

    id: UUID = Field(description="Уникальный идентификатор версии")
    created_at: AwareDatetime = Field(description="Дата создания")

    number: PositiveInt = Field(description="Порядковый номер версии")
    status: VersionStatus = Field(description="Текущий статус версии")
    original_filename: FilePathStr = Field(description="Оригинальное имя файла")

    meta: AssetMeta | None = Field(
        default=None,
        description="Нормализованные технические метаданные",
    )
    raw_meta: dict[str, JsonValue] | None = Field(
        default=None,
        description="Исходные сырые метаданные",
    )

    object: ObjectDTO = Field(description="Ссылка на объект в хранилище")
    derivatives: dict[str, ObjectDTO] = Field(
        default_factory=dict,
        description="Производные от текущей версии",
    )

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

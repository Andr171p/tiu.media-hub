from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
)
from pydantic.alias_generators import to_camel

from src.core.common.types import Str255

from .custom_meta_validation import CustomMeta
from .meta import AssetMeta
from .models import AssetStatus, VersionStatus
from .types import FilePathStr


class CreateAssetDTO(BaseModel):
    """Создание медиа-актива с первой версией."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    collection_id: UUID = Field(description="Коллекция, в которой создаётся актив")

    title: Str255 = Field(
        description="Название медиа-актива",
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
        description="Пользовательские метаданные актива",
    )
    object_id: UUID = Field(description="Идентификатор сохранённого объекта")
    original_filename: FilePathStr = Field(
        description="Оригинальное имя файла в контексте данной версии",
    )


class UpdateAssetDTO(BaseModel):
    """Частичное обновление медиа актива."""

    collection_id: UUID = Field(description="Идентификатор коллекции, в котрой находиться актив")
    title: Str255 | None = None
    description: str | None = Field(default=None, max_length=5000)
    custom_meta: CustomMeta | None = None
    status: AssetStatus | None = None


class AssetResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID = Field(description="Уникальный идентификатор медиа актива")
    created_at: AwareDatetime = Field(alias="createdAt", description="Дата создания")
    updated_at: AwareDatetime = Field(alias="updatedAt", description="Дата последнего обновления")

    collection_id: UUID = Field(
        description="Идентификатор коллекции, в которой находится медиа актив",
    )
    title: Str255 = Field(description="Заголовок медиа актива")
    description: str | None = Field(default=None, description="Описание и контекст медиа-актива")
    custom_meta: CustomMeta = Field(
        default_factory=dict,
        description="Пользовательские метаданные актива",
    )

    status: AssetStatus = Field(description="Текущий статус")
    author_id: UUID | None = Field(default=None, description="Пользователь создавший актив")

    current_version_id: UUID | None = Field(
        default=None,
        description="Идентификатор актуальной версии",
    )


class AssetVersionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID = Field(description="Уникальный идентификатор версии")
    created_at: AwareDatetime = Field(description="Дата создания версии")
    updated_at: AwareDatetime = Field(description="Дата последнего обновления")

    asset_id: UUID = Field(description="Идентификатор актива, версией которого он является")
    object_id: UUID = Field(description="Идентификатор сохранённого объекта")

    number: PositiveInt = Field(description="Порядковый номер версии")
    original_filename: FilePathStr = Field(description="Имя файла отображаемое в UI")
    status: VersionStatus = Field(description="Текущий статус")

    meta: AssetMeta | None = Field(default=None, description="Нормализованные метаданные")


class AssetDerivativeResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID = Field(description="Уникальный идентификатор производной от версии")
    created_at: AwareDatetime = Field(description="Дата создания производной актива")
    variant: str = Field(description="Вариант производного от актива", examples=["preview", "gif"])
    object_id: UUID = Field(description="Идентификатор сохранённого объекта")


class CreateAssetResponse(BaseModel):
    """Результат создания актива и его первой версии."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    asset: AssetResponse
    version: AssetVersionResponse


class CreateAssetVersionDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    object_id: UUID = Field(description="Идентификатор сохранённого объекта")
    original_filename: FilePathStr = Field(
        description="Оригинальное имя файла в контексте данной версии",
    )

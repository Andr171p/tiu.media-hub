from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.core.common.types import Str255

from .models import CollectionStatus
from .policies import UploadPolicy

# =================================================================================================
# Collection DTO
# =================================================================================================


class CreateCollectionDTO(BaseModel):
    """Создание коллекции."""

    name: Str255 = Field(description="Название коллекции")
    description: str | None = Field(default=None, description="Описание коллекции")


class UpdateCollectionDTO(BaseModel):
    """Обновление коллекции."""

    name: Str255 | None = Field(default=None, description="Название коллекции")
    description: str | None = Field(default=None, description="Описание коллекции")


class CollectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    class CollectionSettingsResponse(BaseModel):
        upload_policy: UploadPolicy = Field(
            alias="uploadPolicy",
            description="Политика для загрузки файлов",
        )

    id: UUID4 = Field(description="Идентификатор коллекции")
    created_at: AwareDatetime = Field(description="Дата создания")
    updated_at: AwareDatetime = Field(description="Дата обновления")

    name: Str255 = Field(description="Название коллекции")
    description: str | None = Field(default=None, description="Описание коллекции")
    owner_id: UUID4 = Field(description="Идентификатор владельца")
    status: CollectionStatus = Field(description="Текущий статус коллекции")

    settings: CollectionSettingsResponse = Field(description="Настройки коллекции")


# =================================================================================================
# Member DTO
# =================================================================================================


class CreateMemberDTO(BaseModel):
    ...

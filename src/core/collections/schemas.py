from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, NonNegativeInt
from pydantic.alias_generators import to_camel

from src.core.common.types import Str255

from .models import ImageSizeSettings, WatermarkSettings


class CreateCollectionDTO(BaseModel):
    """Создание коллекции."""

    name: Str255 = Field(description="Название коллекции")
    description: str | None = Field(default=None, description="Описание коллекции")


class CollectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    class CollectionSettingsResponse(BaseModel):
        allowed_extensions: list[str] = Field(description="Допустимые разрешения файлов")
        max_file_size: NonNegativeInt = Field(description="Максимальный размер актива в коллекции")

        thumbnail: ImageSizeSettings = Field(description="Настройки для миниатюр")
        preview: ImageSizeSettings = Field(description="Настройки для превью генерации")
        watermark: WatermarkSettings = Field(description="Настройки водяного знака")

    id: UUID4 = Field(description="Идентификатор коллекции")
    created_at: AwareDatetime = Field(description="Дата создания")
    updated_at: AwareDatetime = Field(description="Дата обновления")

    name: Str255 = Field(description="Название коллекции")
    description: str | None = Field(default=None, description="Описание коллекции")
    owner_id: UUID4 = Field(description="Идентификатор владельца")
    is_active: bool = Field(description="Активна ли коллекция")

    settings: CollectionSettingsResponse = Field(description="Настройки медиа коллекции")

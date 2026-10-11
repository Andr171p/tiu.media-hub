from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt
from pydantic.alias_generators import to_camel


class Schema(BaseModel):
    """Базовая схема API: camelCase в JSON, snake_case в Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class PageParams(Schema):
    limit: PositiveInt = Field(default=50, le=200, description="Размер страницы")
    offset: NonNegativeInt = Field(default=0, description="Смещение")


class Page[T](Schema):
    items: list[T]
    total: NonNegativeInt = Field(description="Общее количество элементов")
    limit: PositiveInt
    offset: NonNegativeInt


class QueuedResponse(Schema):
    """Операция принята и выполняется в фоне."""

    task: str = Field(description="Имя поставленной задачи")


__all__ = ["Page", "PageParams", "QueuedResponse", "Schema"]

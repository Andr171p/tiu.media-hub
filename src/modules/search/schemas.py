from typing import Annotated

from uuid import UUID

from pydantic import Field, NonNegativeInt, PositiveInt, StringConstraints

from src.core.common.schemas import Schema
from src.modules.assets import AssetKind, AssetResponse


class SearchDTO(Schema):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] = Field(
        description="Запрос на естественном языке: ищется и по смыслу изображения, и по тексту",
        examples=["студенты на выпускном у главного корпуса"],
    )
    collection_ids: list[UUID] | None = Field(default=None, description="Искать только в этих коллекциях")
    kinds: list[AssetKind] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, max_length=10, description="Все указанные теги обязательны")
    limit: PositiveInt = Field(default=30, le=100)
    offset: NonNegativeInt = Field(default=0, le=1000)


class SearchResponse(Schema):
    items: list[AssetResponse]
    limit: int
    offset: int
    has_more: bool


class ReindexResponse(Schema):
    queued: NonNegativeInt = Field(description="Поставлено задач в очередь")

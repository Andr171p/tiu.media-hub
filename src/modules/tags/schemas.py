from typing import Annotated

from uuid import UUID

from pydantic import Field, NonNegativeInt, StringConstraints

from src.core.common.schemas import Schema

type TagPrompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TagResponse(Schema):
    id: UUID
    name: str
    auto_assign: bool
    prompt: str | None = None
    usage_count: NonNegativeInt = 0


class CreateTagDTO(Schema):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    auto_assign: bool = Field(default=True, description="Назначать автоматически по содержимому изображения")
    prompt: TagPrompt | None = Field(
        default=None,
        description="Описание для автотегирования, если одного имени мало",
        examples=["фотография студентов в аудитории"],
    )


class UpdateTagDTO(Schema):
    auto_assign: bool | None = None
    prompt: TagPrompt | None = None

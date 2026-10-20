from collections.abc import Sequence

from ddf.application.dtos import Page
from ddf.application.dtos.pagination import CursorMeta
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """DTO публичного API: JSON в camelCase, в Python — snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class CursorPage[T](CamelModel):
    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = Field(default=None, description="Курсор следующей страницы")
    has_next: bool = Field(description="Есть ли следующая страница")

    @classmethod
    def build(cls, page: Page[object], items: Sequence[T]) -> CursorPage[T]:
        """Страница с уже преобразованными элементами и навигацией исходной страницы."""

        if not isinstance(page.meta, CursorMeta):
            raise TypeError("Cursor pagination expected.")

        return cls(items=list(items), next_cursor=page.meta.next_cursor, has_next=page.meta.has_next)

from typing import Annotated, Any

from pydantic import BaseModel
from sqlalchemy import TEXT, Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import mapped_column

type IntNull = Annotated[int | None, mapped_column(nullable=True)]
type FloatNull = Annotated[float | None, mapped_column(nullable=True)]
type TextNull = Annotated[str | None, mapped_column(TEXT, nullable=True)]
type StrNull = Annotated[str | None, mapped_column(nullable=True)]
type StrUnique = Annotated[str, mapped_column(unique=True)]
type ListStr = Annotated[list[str], mapped_column(ARRAY(TEXT), default=[])]


class PydanticJSONB(TypeDecorator):
    """Кастомный тип для автоматической сериализации Pydantic-моделей в JSONB."""

    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_model: type[BaseModel]) -> None:
        super().__init__()
        self.pydantic_model = pydantic_model

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> Any:  # noqa: PLR6301, ARG002, RUF105
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")

        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002, RUF105
        if value is not None:
            return self.pydantic_model.model_validate(value)
        return value


__all__ = [
    "FloatNull",
    "IntNull",
    "ListStr",
    "PydanticJSONB",
    "StrNull",
    "StrUnique",
    "TextNull",
]

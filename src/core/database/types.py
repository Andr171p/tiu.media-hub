from typing import Annotated, Any

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import TEXT, DateTime, Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import mapped_column

type IntNull = Annotated[int | None, mapped_column(nullable=True)]
type FloatNull = Annotated[float | None, mapped_column(nullable=True)]

type DatetimeTz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
type DatetimeTzNull = Annotated[
    datetime | None,
    mapped_column(DateTime(timezone=True), nullable=True),
]

type TextNull = Annotated[str | None, mapped_column(TEXT, nullable=True)]
type StrNull = Annotated[str | None, mapped_column(nullable=True)]
type StrUnique = Annotated[str, mapped_column(unique=True)]

type ListStr = Annotated[list[str], mapped_column(ARRAY(TEXT), default=[])]

type UuidNull = Annotated[
    uuid.UUID | None,
    mapped_column(UUID[uuid.UUID](as_uuid=True), nullable=True)
]


class PydanticJSONB(TypeDecorator):
    """Кастомный тип для автоматической сериализации Pydantic-моделей в JSONB."""

    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_model: type[BaseModel]) -> None:
        super().__init__()
        self.pydantic_model = pydantic_model

    def process_bind_param(self, value: Any | None, dialect: Dialect) -> Any:  # noqa: ARG002
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")

        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002
        if value is not None:
            return self.pydantic_model.model_validate(value)
        return value


__all__ = [
    "DatetimeTz",
    "DatetimeTzNull",
    "FloatNull",
    "IntNull",
    "ListStr",
    "PydanticJSONB",
    "StrNull",
    "StrUnique",
    "TextNull",
    "UuidNull",
]

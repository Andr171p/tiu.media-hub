from typing import Annotated, Any

from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import TEXT, DateTime, Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

type DatetimeTz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
type DatetimeTzNull = Annotated[datetime | None, mapped_column(DateTime(timezone=True), nullable=True)]

type TextNull = Annotated[str | None, mapped_column(TEXT, nullable=True)]
type StrNull = Annotated[str | None, mapped_column(nullable=True)]
type StrUnique = Annotated[str, mapped_column(unique=True)]


class PydanticJSONB(TypeDecorator[Any]):
    """
    JSONB-колонка с типизированным содержимым: модель, список моделей или discriminated union.
    Значение валидируется при чтении, поэтому в Python всегда приходит объект нужного типа.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, type_: Any) -> None:
        super().__init__()
        self._type = type_
        self._adapter: TypeAdapter[Any] = TypeAdapter(type_)

    @property
    def python_type(self) -> Any:
        return self._type

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:  # noqa: ARG002
        if value is None:
            return None
        return self._adapter.dump_python(self._adapter.validate_python(value), mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:  # noqa: ARG002
        if value is None:
            return None
        return self._adapter.validate_python(value)


__all__ = [
    "DatetimeTz",
    "DatetimeTzNull",
    "PydanticJSONB",
    "StrNull",
    "StrUnique",
    "TextNull",
]

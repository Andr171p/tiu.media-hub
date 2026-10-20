"""Сериализация value objects домена в JSONB через pydantic (dataclass ↔ JSON)."""

from typing import Any

from functools import cache

from pydantic import TypeAdapter


@cache
def _adapter(type_: Any) -> TypeAdapter[Any]:
    return TypeAdapter(type_)


def to_json(type_: Any, value: Any) -> Any:
    return _adapter(type_).dump_python(value, mode="json")


def from_json(type_: Any, data: Any) -> Any:
    return _adapter(type_).validate_python(data)


__all__ = ["from_json", "to_json"]

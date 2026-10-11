from collections.abc import Callable, Mapping, Sequence
from datetime import date

from pydantic import JsonValue

from src.core.common.exceptions import InvalidDataError

from .settings import MetadataField, MetadataFieldType

type CustomMeta = dict[str, JsonValue]

_MAX_TEXT_LENGTH = 2000


def _text(value: JsonValue, _: MetadataField) -> JsonValue:
    if not isinstance(value, str) or len(value) > _MAX_TEXT_LENGTH:
        raise ValueError(f"Expected text up to {_MAX_TEXT_LENGTH} characters.")
    return value.strip()


def _number(value: JsonValue, _: MetadataField) -> JsonValue:
    # bool — подкласс int, но числом не считается
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Expected a number.")
    return value


def _date(value: JsonValue, _: MetadataField) -> JsonValue:
    if not isinstance(value, str):
        raise ValueError("Expected a date in YYYY-MM-DD format.")
    return date.fromisoformat(value).isoformat()


def _boolean(value: JsonValue, _: MetadataField) -> JsonValue:
    if not isinstance(value, bool):
        raise ValueError("Expected true or false.")
    return value


def _choice(value: JsonValue, field: MetadataField) -> JsonValue:
    if not field.multiple:
        if value not in field.options:
            raise ValueError("Unknown option.")
        return value

    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Expected a list of options.")
    if unknown := [item for item in value if item not in field.options]:
        raise ValueError(f"Unknown options: {unknown}.")
    return list(dict.fromkeys(value))


_NORMALIZERS: dict[MetadataFieldType, Callable[[JsonValue, MetadataField], JsonValue]] = {
    MetadataFieldType.TEXT: _text,
    MetadataFieldType.NUMBER: _number,
    MetadataFieldType.DATE: _date,
    MetadataFieldType.BOOLEAN: _boolean,
    MetadataFieldType.CHOICE: _choice,
}


def _is_empty(value: JsonValue) -> bool:
    return value is None or value in ("", [])


def validate_custom_meta(fields: Sequence[MetadataField], values: Mapping[str, JsonValue]) -> CustomMeta:
    """
    Проверяет и нормализует значения по схеме коллекции.
    Пустые значения удаляются; неизвестные ключи и пропущенные обязательные поля — ошибка.
    """

    by_key = {field.key: field for field in fields}
    errors: dict[str, str] = {key: "Unknown field." for key in values if key not in by_key}
    result: CustomMeta = {}

    for key, field in by_key.items():
        value = values.get(key)

        if _is_empty(value):
            if field.required:
                errors[key] = "Field is required."
            continue

        try:
            result[key] = _NORMALIZERS[field.type](value, field)
        except ValueError as exc:
            errors[key] = str(exc)

    if errors:
        raise InvalidDataError("Custom metadata does not match the collection schema.", details=errors)

    return result


def missing_required_fields(fields: Sequence[MetadataField], values: Mapping[str, JsonValue]) -> list[str]:
    """Обязательные поля без значения: схема могла измениться после заполнения актива."""

    return [field.key for field in fields if field.required and _is_empty(values.get(field.key))]


__all__ = ["CustomMeta", "missing_required_fields", "validate_custom_meta"]

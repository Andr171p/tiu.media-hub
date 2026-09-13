from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import JsonValue

from .exceptions import InvalidCustomMetaError, InvalidMetaSchemaError

type MetaSchema = dict[str, JsonValue]
type CustomMeta = dict[str, JsonValue]


def validate_meta_schema(schema: MetaSchema) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InvalidMetaSchemaError("Invalid custom metadata schema.") from exc


def validate_custom_meta(schema: MetaSchema, custom_meta: CustomMeta) -> None:
    try:
        Draft202012Validator(schema).validate(custom_meta)
    except ValidationError as exc:
        raise InvalidCustomMetaError(exc.message) from exc


__all__ = ["CustomMeta", "MetaSchema", "validate_custom_meta", "validate_meta_schema"]

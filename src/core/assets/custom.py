"""
Конструктор для кастомных метаданных.
"""

from typing import Annotated, Literal

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

type MetaKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]


class MetadField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: MetaKey
    label: str = Field(min_length=1, max_length=255,)

    description: str | None = None

    required: bool = False
    multiple: bool = False

    searchable: bool = True
    filterable: bool = True


class TextMetaField(MetadField):
    type: Literal["text"] = "text"

    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1)

    pattern: str | None = None


class IntegerMetaField(MetadField):
    type: Literal["integer"] = "integer"

    minimum: int | None = None
    maximum: int | None = None


class DecimalMetaField(MetadField):
    type: Literal["decimal"] = "decimal"

    minimum: Decimal | None = None
    maximum: Decimal | None = None


class BooleanMetaField(MetadField):
    type: Literal["boolean"] = "boolean"


class DateMetaField(MetadField):
    type: Literal["date"] = "date"


class DateTimeMetaField(MetadField):
    type: Literal["datetime"] = "datetime"


class EnumMetaField(MetadField):
    type: Literal["enum"] = "enum"

    options: frozenset[str] = Field(min_length=1)


type MetaFieldDefinition = Annotated[
    TextMetaField
    | IntegerMetaField
    | DecimalMetaField
    | BooleanMetaField
    | DateMetaField
    | DateTimeMetaField
    | EnumMetaField,
    Field(discriminator="type"),
]

from typing import Literal

from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatchcase
from uuid import UUID

from ddf.domain.exceptions import InvariantViolationError
from ddf.domain.models import AggregateRoot, Entity

DEFAULT_ALLOWED_TYPES = frozenset({"image/*", "video/*", "audio/*", "application/pdf"})
DEFAULT_MAX_FILE_SIZE = 20 * 1024**3


class Visibility(StrEnum):
    PRIVATE = "private"
    """Только владелец и участники."""

    INTERNAL = "internal"
    """Все сотрудники видят коллекцию на чтение."""


class CollectionRole(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    MANAGER = "manager"


@dataclass(frozen=True, kw_only=True)
class UploadPolicy:
    """Какие файлы принимает коллекция."""

    allowed_types: frozenset[str] = DEFAULT_ALLOWED_TYPES
    """MIME-маски, например ``image/*``."""

    max_file_size: int = DEFAULT_MAX_FILE_SIZE

    def allows(self, content_type: str, size: int) -> bool:
        content_type = content_type.lower()
        return size <= self.max_file_size and any(
            fnmatchcase(content_type, pattern) for pattern in self.allowed_types
        )


type MetadataFieldType = Literal["text", "number", "date", "boolean", "choice"]
type MetadataValue = str | int | float | bool | list[str]
"""Даты хранятся строкой ISO 8601 (``YYYY-MM-DD``)."""


@dataclass(frozen=True, kw_only=True)
class MetadataField:
    """Поле кастомных метаданных: по нему фронт строит форму, а домен проверяет значения."""

    key: str
    label: str
    type: MetadataFieldType
    required: bool = False
    options: tuple[str, ...] = ()
    """Варианты для ``choice``."""

    multiple: bool = False
    """Несколько значений (только ``choice``)."""

    def __post_init__(self) -> None:
        if self.type == "choice" and not self.options:
            raise InvariantViolationError(f"Choice field {self.key!r} requires options.")

        if self.type != "choice" and (self.options or self.multiple):
            raise InvariantViolationError(f"Only choice fields can have options: {self.key!r}.")


@dataclass(kw_only=True)
class Collection(AggregateRoot):
    """Граница доступа: участники, правила загрузки и схема метаданных активов."""

    name: str
    description: str | None = None
    owner_id: UUID
    visibility: Visibility = Visibility.PRIVATE
    upload_policy: UploadPolicy = field(default_factory=UploadPolicy)
    metadata_schema: tuple[MetadataField, ...] = ()

    def __post_init__(self) -> None:
        _ensure_unique_keys(self.metadata_schema)

    def change_metadata_schema(self, schema: tuple[MetadataField, ...]) -> None:
        _ensure_unique_keys(schema)
        self.metadata_schema = schema


def _ensure_unique_keys(schema: tuple[MetadataField, ...]) -> None:
    keys = [metadata_field.key for metadata_field in schema]
    if len(keys) != len(set(keys)):
        raise InvariantViolationError("Metadata field keys must be unique.")


@dataclass(kw_only=True)
class CollectionMember(Entity):
    """Участник коллекции. Владелец не хранится участником: его права следуют из ``owner_id``."""

    collection_id: UUID
    user_id: UUID
    role: CollectionRole

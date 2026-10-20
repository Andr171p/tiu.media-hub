import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import PurePath
from uuid import UUID

from ddf.domain.exceptions import InvalidStateError, InvariantViolationError

from src.domain.collections import Collection, MetadataField, MetadataValue

from .events import AssetMoved, AssetRestored, AssetTrashed, AssetVersionAdded
from .models import Asset, AssetKind, AssetVersion, StoredFile

MAX_TAG_LENGTH = 64
MAX_TAGS = 100


def create_asset(
    collection: Collection,
    file: StoredFile,
    *,
    created_by: UUID,
    title: str | None = None,
    source_version_id: UUID | None = None,
    asset_id: UUID | None = None,
    version_id: UUID | None = None,
) -> tuple[Asset, AssetVersion]:
    """
    Создаёт актив с первой версией; название по умолчанию — имя файла без расширения.
    Идентификаторы можно задать заранее, чтобы повторная операция не создала дубликат.
    """

    asset_id = asset_id or uuid.uuid7()
    version = AssetVersion(
        id=version_id or uuid.uuid7(),
        asset_id=asset_id,
        number=1,
        file=file,
        created_by=created_by,
        source_version_id=source_version_id,
    )
    asset = Asset(
        id=asset_id,
        collection_id=collection.id,
        title=title or PurePath(file.name).stem or file.name,
        kind=AssetKind.of(file.content_type),
        created_by=created_by,
        current_version_id=version.id,
    )
    asset.register_event(AssetVersionAdded(asset_id=asset.id, version_id=version.id))

    return asset, version


def normalize_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Теги в нижнем регистре без повторов, порядок сохраняется."""

    normalized = dict.fromkeys(
        " ".join(tag.split()).lower()[:MAX_TAG_LENGTH] for tag in tags if tag and not tag.isspace()
    )
    return tuple(normalized)[:MAX_TAGS]


def validate_metadata(
    schema: Iterable[MetadataField],
    values: Mapping[str, MetadataValue],
) -> dict[str, MetadataValue]:
    """Проверяет значения по схеме коллекции; ключи вне схемы отбрасываются."""

    result: dict[str, MetadataValue] = {}

    for metadata_field in schema:
        value = values.get(metadata_field.key)

        if value is None or value in ("", []):
            if metadata_field.required:
                raise InvariantViolationError(f"Metadata field {metadata_field.key!r} is required.")
            continue

        if not _matches(metadata_field, value):
            raise InvariantViolationError(f"Invalid value for metadata field {metadata_field.key!r}.")

        result[metadata_field.key] = value

    return result


def _matches(metadata_field: MetadataField, value: MetadataValue) -> bool:
    match metadata_field.type:
        case "text":
            return isinstance(value, str)
        case "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        case "boolean":
            return isinstance(value, bool)
        case "date":
            return isinstance(value, str) and _is_iso_date(value)
        case "choice" if metadata_field.multiple:
            return isinstance(value, list) and all(item in metadata_field.options for item in value)
        case "choice":
            return isinstance(value, str) and value in metadata_field.options

    return False


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def move_asset(asset: Asset, collection: Collection) -> None:
    if asset.is_deleted:
        raise InvalidStateError("Trashed asset cannot be moved.")

    if asset.collection_id == collection.id:
        return

    keys = {metadata_field.key for metadata_field in collection.metadata_schema}
    asset.collection_id = collection.id
    asset.metadata = {key: value for key, value in asset.metadata.items() if key in keys}
    asset.updated_at = datetime.now(UTC)
    asset.register_event(AssetMoved(asset_id=asset.id, collection_id=collection.id))


def trash_asset(asset: Asset) -> None:
    if asset.is_deleted:
        return

    asset.deleted_at = asset.updated_at = datetime.now(UTC)
    asset.register_event(AssetTrashed(asset_id=asset.id))


def restore_asset(asset: Asset) -> None:
    if not asset.is_deleted:
        return

    asset.deleted_at = None
    asset.updated_at = datetime.now(UTC)
    asset.register_event(AssetRestored(asset_id=asset.id))


__all__ = [
    "create_asset",
    "move_asset",
    "normalize_tags",
    "restore_asset",
    "trash_asset",
    "validate_metadata",
]

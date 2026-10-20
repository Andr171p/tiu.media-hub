from typing import ClassVar

from dataclasses import dataclass
from uuid import UUID

from ddf.domain.events import Event


@dataclass(frozen=True, kw_only=True)
class AssetVersionAdded(Event):
    """Загружен файл новой версии: нужна обработка (метаданные, превью, прокси)."""

    event_type: ClassVar[str] = "assets.version_added"

    asset_id: UUID
    version_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetVersionProcessed(Event):
    """Готовы превью версии: можно индексировать для поиска и анализировать ИИ."""

    event_type: ClassVar[str] = "assets.version_processed"

    asset_id: UUID
    version_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetCurrentVersionChanged(Event):
    event_type: ClassVar[str] = "assets.current_version_changed"

    asset_id: UUID
    version_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetMoved(Event):
    event_type: ClassVar[str] = "assets.moved"

    asset_id: UUID
    collection_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetTrashed(Event):
    event_type: ClassVar[str] = "assets.trashed"

    asset_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetRestored(Event):
    event_type: ClassVar[str] = "assets.restored"

    asset_id: UUID


@dataclass(frozen=True, kw_only=True)
class AssetPurged(Event):
    """Актив удалён окончательно вместе с файлами."""

    event_type: ClassVar[str] = "assets.purged"

    asset_id: UUID


__all__ = [
    "AssetCurrentVersionChanged",
    "AssetMoved",
    "AssetPurged",
    "AssetRestored",
    "AssetTrashed",
    "AssetVersionAdded",
    "AssetVersionProcessed",
]

from typing import Literal

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from ddf.application.dtos import CursorPagination, Page
from ddf.application.repositories import Repository

from src.domain.assets import Asset, AssetKind, AssetVersion, LicenseStatus, Upload


class AssetRepository(Repository[Asset]):
    async def read(self, uid: UUID, with_lock: bool = False) -> Asset | None:
        raise NotImplementedError

    async def find_trashed_before(self, moment: datetime, *, limit: int) -> Sequence[Asset]:
        raise NotImplementedError


class AssetVersionRepository(Repository[AssetVersion]):
    async def list_by_asset(self, asset_id: UUID) -> Sequence[AssetVersion]:
        """Версии актива, новые первыми."""
        raise NotImplementedError


class UploadRepository(Repository[Upload]):
    async def find_expired(self, now: datetime, *, limit: int) -> Sequence[Upload]:
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class AssetFilter:
    collection_ids: Sequence[UUID] | None
    """Доступные коллекции; ``None`` — все."""

    kinds: Sequence[AssetKind] = ()
    tags: Sequence[str] = ()
    """Активы со всеми перечисленными тегами."""

    created_by: UUID | None = None
    person_id: UUID | None = None
    license: LicenseStatus | Literal["none"] | None = None
    usable_on: date | None = None
    """Только активы, которые можно использовать в этот день: лицензия не истекла и уже действует."""

    trashed: bool = False
    asset_ids: Sequence[UUID] | None = field(default=None)


class AssetQueryRepository:
    async def find(
        self,
        asset_filter: AssetFilter,
        pagination: CursorPagination,
        *,
        sort: Literal["created_at", "updated_at"] = "created_at",
    ) -> Page[Asset]:
        raise NotImplementedError


__all__ = [
    "AssetFilter",
    "AssetQueryRepository",
    "AssetRepository",
    "AssetVersionRepository",
    "UploadRepository",
]

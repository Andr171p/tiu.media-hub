"""Выборки активов с отношениями, нужными для ответа API."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.cdn import CdnClient
from src.modules.collections import CollectionStats
from src.modules.tags import AssetTag

from .models import Asset, AssetStatus, AssetVersion, Rendition, RenditionKind, VersionStatus

VERSION_OPTIONS = (
    selectinload(AssetVersion.renditions),
    selectinload(AssetVersion.object),
    selectinload(AssetVersion.creator),
)


def select_assets() -> Select[tuple[Asset]]:
    return (
        select(Asset)
        .where(Asset.deleted_at.is_(None))
        .options(
            selectinload(Asset.author),
            selectinload(Asset.tags).selectinload(AssetTag.tag),
            selectinload(Asset.current_version).options(*VERSION_OPTIONS),
        )
        .execution_options(populate_existing=True)
    )


async def get_pending_versions(session: AsyncSession, assets: Iterable[Asset]) -> dict[UUID, AssetVersion]:
    """Последняя версия каждого актива, если она ещё не готова (обрабатывается или отклонена)."""

    if not (ids := [asset.id for asset in assets]):
        return {}

    stmt = (
        select(AssetVersion)
        .where(AssetVersion.asset_id.in_(ids))
        .distinct(AssetVersion.asset_id)
        .order_by(AssetVersion.asset_id, AssetVersion.number.desc())
        .options(*VERSION_OPTIONS)
    )
    return {
        version.asset_id: version
        for version in await session.scalars(stmt)
        if version.status is not VersionStatus.READY
    }


async def get_collection_stats(
    session: AsyncSession,
    cdn: CdnClient,
    collection_ids: Iterable[UUID],
) -> dict[UUID, CollectionStats]:
    """Количество активов и обложка (миниатюра последнего актива) для карточек коллекций."""

    if not (ids := list(collection_ids)):
        return {}

    visible = (
        Asset.collection_id.in_(ids),
        Asset.deleted_at.is_(None),
        Asset.status == AssetStatus.ACTIVE,
    )

    counts = dict(
        (
            await session.execute(
                select(Asset.collection_id, func.count()).where(*visible).group_by(Asset.collection_id)
            )
        )
        .tuples()
        .all(),
    )
    covers = dict(
        (
            await session.execute(
                select(Asset.collection_id, Rendition.storage_key)
                .join(Rendition, Rendition.version_id == Asset.current_version_id)
                .where(*visible, Rendition.kind == RenditionKind.THUMBNAIL)
                .distinct(Asset.collection_id)
                .order_by(Asset.collection_id, Asset.created_at.desc()),
            )
        )
        .tuples()
        .all(),
    )

    return {
        collection_id: CollectionStats(
            asset_count=counts.get(collection_id, 0),
            cover_url=cdn.url(key) if (key := covers.get(collection_id)) else None,
        )
        for collection_id in ids
    }


__all__ = ["VERSION_OPTIONS", "get_collection_stats", "get_pending_versions", "select_assets"]

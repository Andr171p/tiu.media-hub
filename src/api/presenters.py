"""Сборка ответов API из нескольких модулей: права, ожидающие версии, статистика коллекций."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import AuthUser
from src.core.cdn import CdnClient
from src.modules import assets, collections
from src.modules.assets import Asset, AssetContext, AssetResponse
from src.modules.collections import CollectionAccess, CollectionResponse, CollectionRole


async def present_assets(
    db: AsyncSession,
    cdn: CdnClient,
    items: Sequence[Asset],
    *,
    user: AuthUser | None,
) -> list[AssetResponse]:
    """Ответы по активам из любых коллекций. ``user=None`` — доверенный сервис, только чтение."""

    collection_ids = {asset.collection_id for asset in items}
    if user is not None:
        accesses = await collections.get_accesses(db, collection_ids, user)
    else:
        found = await collections.get_collections(db, collection_ids)
        accesses = {key: CollectionAccess(value, CollectionRole.VIEWER) for key, value in found.items()}

    pending = await assets.get_pending_versions(db, items)

    return [
        assets.to_asset_response(
            asset,
            cdn=cdn,
            settings=access.collection.settings,
            can_edit=user is not None and AssetContext(asset, access, user).can_edit,
            pending_version=pending.get(asset.id),
        )
        for asset in items
        if (access := accesses.get(asset.collection_id)) is not None
    ]


async def present_asset(db: AsyncSession, cdn: CdnClient, context: AssetContext) -> AssetResponse:
    pending = await assets.get_pending_versions(db, [context.asset])
    return assets.to_asset_response(
        context.asset,
        cdn=cdn,
        settings=context.access.collection.settings,
        can_edit=context.can_edit,
        pending_version=pending.get(context.asset.id),
    )


async def present_collections(
    db: AsyncSession,
    cdn: CdnClient,
    accesses: Sequence[CollectionAccess],
) -> list[CollectionResponse]:
    stats = await assets.get_collection_stats(db, cdn, (access.collection.id for access in accesses))
    return [
        collections.to_collection_response(access, stats.get(access.collection.id)) for access in accesses
    ]


async def present_collection(
    db: AsyncSession, cdn: CdnClient, access: CollectionAccess
) -> CollectionResponse:
    [response] = await present_collections(db, cdn, [access])
    return response


__all__ = ["present_asset", "present_assets", "present_collection", "present_collections"]

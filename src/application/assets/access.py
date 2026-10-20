from dataclasses import dataclass
from uuid import UUID

from ddf.application.exceptions import NotFoundError

from src.application.auth import AuthUser
from src.application.collections.access import get_collection_access
from src.application.collections.repositories import CollectionRepository
from src.domain.assets import Asset
from src.domain.collections import Collection, Permission

from .repositories import AssetRepository


@dataclass(frozen=True, slots=True)
class AssetAccess:
    asset: Asset
    collection: Collection
    permissions: frozenset[Permission]


async def get_asset_access(
    asset_id: UUID,
    auth: AuthUser,
    permission: Permission = Permission.READ,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    with_lock: bool = False,
) -> AssetAccess:
    """Права на актив следуют из его коллекции."""

    if (asset := await asset_repository.read(asset_id, with_lock=with_lock)) is None:
        raise NotFoundError(f"Asset with ID {asset_id} not found.")

    try:
        access = await get_collection_access(
            asset.collection_id, auth, permission, collection_repository=collection_repository
        )
    except NotFoundError:
        raise NotFoundError(f"Asset with ID {asset_id} not found.") from None

    return AssetAccess(asset=asset, collection=access.collection, permissions=access.permissions)


__all__ = ["AssetAccess", "get_asset_access"]

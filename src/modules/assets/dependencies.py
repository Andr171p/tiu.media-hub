from typing import Annotated

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from src.core.assets.dtos import AssetVersionResponse
from src.core.assets.models import Asset
from src.modules.database import DBSession

from .crud import crud, get_asset_versions


async def _get_asset(db: DBSession, asset_id: UUID) -> Asset:
    asset = await crud.read(db, asset_id)

    if asset is None or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id!r} not found.",
        )

    return asset


async def _get_asset_versions(
    db: DBSession,
    asset_id: UUID,
    offset: Annotated[int, Query(ge=0, description="Смещение")] = 0,
    limit: Annotated[int, Query(ge=0, le=100, description="Лимит элементов")] = 50,
) -> list[AssetVersionResponse]:
    versions = await get_asset_versions(db, asset_id, offset=offset, limit=limit)
    return [AssetVersionResponse.model_validate(version) for version in versions]


asset_depends = Depends(_get_asset)
asset_versions_depends = Depends(_get_asset_versions)

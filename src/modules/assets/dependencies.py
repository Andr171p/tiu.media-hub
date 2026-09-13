from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.core.assets.models import Asset
from src.modules.database import DBSession

from .crud import asset_crud


async def get_asset(session: DBSession, asset_id: UUID) -> Asset:
    asset = await asset_crud.read(session, asset_id)

    if asset is None or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id!r} not found.",
        )

    return asset


asset_depends = Depends(get_asset)

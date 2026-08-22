from uuid import UUID

from fastapi import HTTPException, status

from src.core.assets.schemas import AssetResponse
from src.modules.database import DBSession

from .crud import asset_crud


async def get_asset(session: DBSession, asset_id: UUID) -> AssetResponse:
    if (asset := await asset_crud.read(session, asset_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset not found by Id - {asset_id!r}.",
        )

    return AssetResponse.model_validate(asset)

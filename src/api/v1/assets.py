from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.core.assets.schemas import (
    AssetResponse,
    CreateAssetDTO,
    UploadAssetDTO,
    UploadAssetResponse,
)
from src.modules.assets import asset_crud, get_asset, uploading
from src.modules.database import DBSession

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать медиа актив",
)
async def create_asset(session: DBSession, dto: CreateAssetDTO) -> AssetResponse:
    asset = await asset_crud.create(session, dto)
    await session.commit()
    return AssetResponse.model_validate(asset)


@router.post(
    path="/{asset_id}/uploads",
    status_code=status.HTTP_200_OK,
    summary="Инициировать загрузку медиа актива",
)
async def upload_asset(
        session: DBSession, asset_id: UUID, dto: UploadAssetDTO,
) -> UploadAssetResponse:
    return await uploading.init_upload(session, asset_id, dto)


@router.post(
    path="/{asset_id}/uploads/{upload_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Завершить загрузку медиа актива",
)
async def complete_asset_upload(
        session: DBSession, asset_id: UUID, upload_id: UUID,
) -> AssetResponse:
    return await uploading.confirm_upload(session, asset_id, upload_id)


@router.get(
    path="/{asset_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить медиа актив",
)
async def get_asset(asset: AssetResponse = Depends(get_asset)) -> AssetResponse:
    return asset

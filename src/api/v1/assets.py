from uuid import UUID

from fastapi import APIRouter, status

from src.core.assets.dtos import (
    AssetResponse,
    CreateAssetDTO,
    UploadAssetDTO,
    UploadAssetResponse,
)
from src.modules.assets import asset_crud, asset_depends
from src.modules.assets.uploading import confirm_upload, init_upload
from src.modules.auth import CurrentUser, auth_security
from src.modules.database import DBSession

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать медиа актив",
)
async def create_asset(
    session: DBSession,
    dto: CreateAssetDTO,
    user: CurrentUser,
) -> AssetResponse:
    created = await asset_crud.create(session, dto, options=user)
    await session.commit()
    return AssetResponse.model_validate(created)


@router.post(
    path="/{asset_id}/uploads",
    status_code=status.HTTP_200_OK,
    summary="Инициировать загрузку медиа актива",
)
async def upload_asset(
    session: DBSession,
    asset_id: UUID,
    dto: UploadAssetDTO,
    user: CurrentUser,
) -> UploadAssetResponse:
    return await init_upload(session, asset_id, dto, user)


@router.post(
    path="/{asset_id}/uploads/{upload_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Завершить загрузку медиа актива",
)
async def complete_asset_upload(
    session: DBSession,
    asset_id: UUID,
    upload_id: UUID,
    user: CurrentUser,
) -> AssetResponse:
    return await confirm_upload(session, asset_id, upload_id, user)


@router.get(
    path="/{asset_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[auth_security],
    summary="Получить медиа актив",
)
async def get_asset(asset: AssetResponse = asset_depends) -> AssetResponse:
    return asset

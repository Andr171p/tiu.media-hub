from uuid import UUID

from fastapi import APIRouter, status

from src.core.assets.dtos import (
    AssetResponse,
    CreateAssetDTO,
    CreateAssetVersionDTO,
    UpdateAssetDTO,
    UploadAssetDTO,
    UploadResult,
)
from src.core.assets.models import Asset
from src.modules.assets.crud import crud as asset_crud
from src.modules.assets.dependencies import asset_depends
from src.modules.assets.uploading import complete_upload, init_upload
from src.modules.assets.versioning import sync_asset_version
from src.modules.auth.dependencies import (
    CurrentUser,
    auth_client_security,
    auth_security,
    auth_user_security,
)
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


@router.patch(
    path="/{asset_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить медиа актив",
)
async def update_asset(
        session: DBSession,
        dto: UpdateAssetDTO,
        user: CurrentUser,
        asset: Asset = asset_depends,
) -> AssetResponse:
    updated = await asset_crud.update(session, asset, dto)
    await session.commit()
    return AssetResponse.model_validate(updated)


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
) -> UploadResult:
    return await init_upload(session, asset_id, dto, user)


@router.post(
    path="/{asset_id}/uploads/{upload_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[auth_user_security],
    summary="Завершить загрузку медиа актива",
)
async def complete_asset_upload(
    session: DBSession,
    asset_id: UUID,
    upload_id: UUID,
) -> AssetResponse:
    return await complete_upload(
        session,
        asset_id=asset_id,
        upload_id=upload_id,
    )


@router.put(
    path="/{asset_id}/uploads/{upload_id}/version",
    status_code=status.HTTP_201_CREATED,
    dependencies=[auth_client_security],
    summary="Создание версии из upload session"
)
async def create_asset_version(
    session: DBSession,
    asset_id: UUID,
    upload_id: UUID,
    dto: CreateAssetVersionDTO,
) -> ...:
    asset_version = await sync_asset_version(session, asset_id, upload_id, dto)
    await session.commit()


@router.patch(
    path="/{asset_id}/versions/{version_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[auth_client_security],
    summary="Обновление версии актива",
)
async def update_asset_version(): ...


@router.get(
    path="/{asset_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[auth_security],
    summary="Получить медиа актив",
)
async def get_asset(asset: AssetResponse = asset_depends) -> AssetResponse:
    return AssetResponse.model_validate(asset)

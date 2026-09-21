from uuid import UUID

from fastapi import APIRouter, status

from src.modules.assets import (
    Asset,
    AssetResponse,
    AssetVersionResponse,
    CreateAssetDTO,
    CreateAssetVersionDTO,
    UpdateAssetDTO,
    asset_depends,
    asset_versions_depends,
    create_asset_version,
    crud,
)
from src.modules.auth import CurrentUser, auth_security
from src.modules.database import DBSession

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать медиа-актив с первой версией",
)
async def create_asset(db: DBSession, dto: CreateAssetDTO, user: CurrentUser) -> AssetResponse:
    asset = await crud.create(db, dto, user)
    await db.commit()
    return AssetResponse.model_validate(asset)


@router.get(
    "/{asset_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[auth_security],
    summary="Получить медиа актив",
)
async def get_asset(asset: Asset = asset_depends) -> AssetResponse:
    return AssetResponse.model_validate(asset)


@router.patch(
    "/{asset_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить медиа актив",
)
async def update_asset(
    db: DBSession,
    dto: UpdateAssetDTO,
    user: CurrentUser,
    asset: Asset = asset_depends,
) -> AssetResponse:
    updated = await crud.update(db, asset, dto, user)
    await db.commit()
    return AssetResponse.model_validate(updated)


@router.post(
    "/{asset_id}/versions",
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую версию медиа актива",
)
async def create_asset_version_(
    db: DBSession,
    asset_id: UUID,
    dto: CreateAssetVersionDTO,
    user: CurrentUser,
) -> AssetVersionResponse:
    version = await create_asset_version(db, asset_id, dto, user)
    await db.commit()
    return AssetVersionResponse.model_validate(version)


@router.get(
    "/{asset_id}/versions",
    status_code=status.HTTP_200_OK,
    summary="Получить версии медиа актива",
)
async def get_asset_versions_(
    versions: list[AssetVersionResponse] = asset_versions_depends,
) -> list[AssetVersionResponse]:
    return versions

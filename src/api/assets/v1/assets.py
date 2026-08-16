from fastapi import APIRouter, status

from src.core.assets.schemas import AssetCreate, AssetVersionUpload, AssetVersionUploadResponse
from src.services.database import DBSession
from src.services.assets.crud import crud as asset_crud

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=...,
    summary="Создать медиа актив"
)
async def create_asset(session: DBSession, dto: AssetCreate):
    asset = await asset_crud.create(session, dto)
    await session.commit()


@router.post(
    path="/{asset_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=AssetVersionUploadResponse,
    summary="Генерирует URL для direct upload"
)
async def upload_asset_version(dto: AssetVersionUpload) -> AssetVersionUploadResponse: ...


@router.post(
    path="/{asset_id}/versions/{version_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=...,
    summary="Подтверждение загрузки медиа актива"
)
async def complete_asset_version_uploading(): ...

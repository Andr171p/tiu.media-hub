from fastapi import APIRouter, status

from src.core.assets.schemas import AssetResponse, CreateAssetDTO
from src.modules.assets.crud import asset_crud
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
    summary="",
)
async def upload_asset(): ...


@router.post(
    path="/{asset_id}/uploads/{upload_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    summary="",
)
async def complete_asset_upload(): ...

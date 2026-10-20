from uuid import UUID

from fastapi import APIRouter

from src.api.dependencies.auth import CurrentService
from src.api.dependencies.repositories import AssetRepositoryDep, VersionRepositoryDep
from src.api.dependencies.services import MediaUrlsDep, OriginalsDep
from src.application.assets import usecases

router = APIRouter(prefix="/assets", tags=["Сервисы"])


@router.get(
    "/{asset_id}",
    summary="Актив со ссылкой на оригинал",
    description="Client Credentials, роль assets:read. Для интеграций (база знаний, сайт).",
)
async def get_asset(
    asset_id: UUID,
    _: CurrentService,
    assets: AssetRepositoryDep,
    versions: VersionRepositoryDep,
    originals: OriginalsDep,
    media_urls: MediaUrlsDep,
) -> usecases.ServiceAssetResponse:
    return await usecases.get_asset_for_service(
        asset_id,
        asset_repository=assets,
        version_repository=versions,
        originals=originals,
        media_urls=media_urls,
    )

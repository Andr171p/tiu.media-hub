from uuid import UUID

from fastapi import APIRouter

from src.api.dependencies import DBSession, S3Dep, SearchDep, UploadConfigDep
from src.api.presenters import PresenterDep
from src.modules import assets
from src.modules.assets import AssetResponse, DownloadResponse, versions
from src.modules.search import SearchDTO, SearchResponse, build_scope

router = APIRouter(tags=["Client: Assets"])


@router.get("/assets/{asset_id}", summary="Получить актив")
async def get_asset(db: DBSession, presenter: PresenterDep, asset_id: UUID) -> AssetResponse:
    [response] = await presenter.assets(db, [await assets.get_asset(db, asset_id)], user=None)
    return response


@router.get("/assets/{asset_id}/versions/{version_id}/download", summary="Скачать оригинал версии")
async def download_version(
    db: DBSession,
    s3: S3Dep,
    config: UploadConfigDep,
    asset_id: UUID,
    version_id: UUID,
) -> DownloadResponse:
    version = await versions.get_asset_version(db, asset_id, version_id)
    url = await s3.create_download_url(
        version.object.storage_key,
        filename=version.original_filename,
        expires_in=config.download_url_expires_in,
    )
    return DownloadResponse(url=url, filename=version.original_filename, kind="original")


@router.post("/search", summary="Поиск активов во всех коллекциях")
async def search_assets(
    db: DBSession, presenter: PresenterDep, search: SearchDep, dto: SearchDTO
) -> SearchResponse:
    items, has_more = await search.search(db, dto, build_scope(dto, allowed=None))
    return SearchResponse(
        items=await presenter.assets(db, items, user=None),
        limit=dto.limit,
        offset=dto.offset,
        has_more=has_more,
    )

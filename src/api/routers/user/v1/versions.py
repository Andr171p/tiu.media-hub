from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import AssetContextDep, CdnDep, DBSession, S3Dep, UploadConfigDep
from src.modules.assets import (
    CreateVersionDTO,
    DownloadResponse,
    VersionResponse,
    to_version_response,
    versions,
)
from src.worker.indexing import index_asset
from src.worker.processing import process_version

router = APIRouter(prefix="/assets/{asset_id}/versions", tags=["Versions"])


@router.get("", summary="История версий")
async def list_versions(db: DBSession, cdn: CdnDep, context: AssetContextDep) -> list[VersionResponse]:
    current_id = context.asset.current_version_id
    return [
        to_version_response(version, cdn, is_current=version.id == current_id)
        for version in await versions.list_versions(db, context)
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить новую версию",
    description="Новый файл или правка в редакторе (sourceVersionId). Текущей станет после обработки.",
)
async def add_version(
    db: DBSession,
    cdn: CdnDep,
    context: AssetContextDep,
    dto: CreateVersionDTO,
) -> VersionResponse:
    version = await versions.add_version(db, context, dto)
    await db.commit()
    await process_version.kiq(str(version.id))

    return to_version_response(await versions.get_version(db, context, version.id), cdn, is_current=False)


@router.post(
    "/{version_id}/promote",
    summary="Сделать версию текущей",
    description="Откат к предыдущей версии или возврат к более новой. История не теряется.",
)
async def promote_version(
    db: DBSession, cdn: CdnDep, context: AssetContextDep, version_id: UUID
) -> VersionResponse:
    await versions.promote_version(db, context, version_id)
    await db.commit()
    await index_asset.kiq(str(context.asset.id), with_image=True)

    return to_version_response(await versions.get_version(db, context, version_id), cdn, is_current=True)


@router.get(
    "/{version_id}/download",
    summary="Скачать версию",
    description="Участникам коллекции — оригинал по временной ссылке, остальным — превью с водяным знаком.",
)
async def download_version(
    db: DBSession,
    s3: S3Dep,
    cdn: CdnDep,
    config: UploadConfigDep,
    context: AssetContextDep,
    version_id: UUID,
) -> DownloadResponse:
    version = await versions.get_version(db, context, version_id)
    return await versions.create_download(context, version, s3=s3, cdn=cdn, config=config)

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.consts import UPLOAD_URL_EXPIRES_IN
from src.core.assets.enums import AssetStatus
from src.core.assets.helpers import build_upload_storage_key, generate_upload_id
from src.core.assets.models import Asset
from src.core.assets.schemas import (
    AssetResponse,
    UpdateAssetDTO,
    UploadAssetDTO,
    UploadAssetResponse,
    UploadInfo,
)
from src.modules.s3 import s3_client
from src.modules.temporal import temporal_client

from .crud import asset_crud


async def _get_asset_or_404(session: AsyncSession, asset_id: UUID) -> Asset:
    if (asset := await asset_crud.read(session, asset_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset not found by Id - {asset_id!r}.",
        )

    return asset


async def init_upload(
        session: AsyncSession, asset_id: UUID, dto: UploadAssetDTO,
) -> UploadAssetResponse:
    """Инициирует прямую загрузку медиа актива в хранилище."""

    asset = await _get_asset_or_404(session, asset_id)

    if asset.status != AssetStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Asset is not in 'PENDING' status.",
        )

    upload_id = generate_upload_id(
        asset_id=asset_id,
        filename=dto.filename,
        mime_type=dto.mime_type,
        size=dto.size,
    )
    storage_key = build_upload_storage_key(
        asset_id=asset_id, upload_id=upload_id, filename=dto.filename,
    )

    upload_url = await s3_client.create_upload_url(
        storage_key=storage_key,
        mime_type=dto.mime_type,
        expires_in=UPLOAD_URL_EXPIRES_IN,
    )

    context = {**dto.model_dump(), "asset_id": asset_id, "storage_key": storage_key}

    try:
        await temporal_client.start_asset_processing(upload_id=upload_id, context=context)
    except WorkflowAlreadyStartedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset with uploadId - {upload_id!r} is already processed.",
        ) from None

    upload_info = UploadInfo(url=upload_url, expiresIn=UPLOAD_URL_EXPIRES_IN)
    return UploadAssetResponse(uploadId=upload_id, upload=upload_info)


async def confirm_upload(session: AsyncSession, asset_id: UUID, upload_id: UUID) -> AssetResponse:

    if (asset := await asset_crud.read(session, asset_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset not found by Id - {asset_id!r}.",
        )

    dto = UpdateAssetDTO(status=AssetStatus.PROCESSING)
    updated = await asset_crud.update(session, asset, dto=dto)

    await session.commit()

    await temporal_client.complete_asset_upload(upload_id)

    return AssetResponse.model_validate(updated)


__all__ = ["confirm_upload", "init_upload"]

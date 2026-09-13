from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.consts import UPLOAD_URL_EXPIRES_IN
from src.core.assets.dtos import (
    AssetResponse,
    UpdateAssetDTO,
    UploadAssetDTO,
    UploadInfo,
    UploadResult,
)
from src.core.assets.models import Asset, AssetStatus
from src.core.assets.utils import build_storage_key
from src.core.auth.models import User
from src.modules.s3 import s3_client
from src.modules.temporal import temporal_client

from .crud import asset_crud


async def init_upload(asset: Asset, dto: UploadAssetDTO) -> UploadResult:
    """Инициирует прямую загрузку медиа актива в S3 хранилище."""

    upload_id, source_id = uuid4(), uuid4()
    storage_key = build_storage_key(asset.id, source_id)

    upload_url = await s3_client.create_upload_url(
        storage_key=storage_key,
        mime_type=dto.mime_type,
        expires_in=UPLOAD_URL_EXPIRES_IN,
    )
    upload_info = UploadInfo(url=upload_url, expires_in=UPLOAD_URL_EXPIRES_IN)

    return UploadResult(upload_id=upload_id, upload_info=upload_info)


async def complete_upload(asset: Asset, upload_id: UUID) -> AssetResponse:
    update_dto = UpdateAssetDTO(status=AssetStatus.PROCESSING)
    updated = await asset_crud.update(session, asset, dto=update_dto)

    await session.commit()

    await temporal_client.complete_asset_upload(upload_id)

    return AssetResponse.model_validate(updated)


__all__ = ["complete_upload", "init_upload"]

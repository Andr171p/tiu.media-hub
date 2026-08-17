import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.schemas import (
    AssetCreate,
    AssetUploadRequest,
    AssetVersionCreate,
    AssetVersionUploadResponse,
    UploadInfo,
)
from src.core.assets.services import build_original_storage_key, resolve_asset_type
from src.core.auth.models import User
from src.services.s3 import s3_client

from .crud import asset_crud, asset_version_crud


async def init_upload(
        session: AsyncSession, request: AssetUploadRequest, user: User,
) -> AssetVersionUploadResponse:

    asset = await asset_crud.create(
        session,
        dto=AssetCreate(
            title=request.title,
            description=request.description,
            type_=resolve_asset_type(request.file.mime_type),
        ),
        options=user,
    )

    version_id = uuid.uuid4()

    storage_key = build_original_storage_key(asset_id=asset.id, version_id=version_id)
    asset_version = await asset_version_crud.create(
        session,
        dto=AssetVersionCreate(
            asset_id=asset.id,
            version=1,
            storage_key=storage_key,
            original_filename=request.file.filename,
            mime_type=request.file.mime_type,
            size=request.file.size,
        ),
    )

    upload_url = await s3_client.create_upload_url(
        storage_key=storage_key, mime_type=request.file.mime_type,
    )

    await session.commit()

    return AssetVersionUploadResponse(
        asset_id=asset.id,
        version_id=version_id,
        version=asset_version.version,
        status=asset_version.status,
        upload=UploadInfo(url=upload_url, expires_in=...),
    )

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.models import AssetStatus, AssetVersionStatus
from src.core.assets.schemas import (
    AssetCreate,
    AssetUpdate,
    AssetUploadRequest,
    AssetVersionCreate,
    AssetVersionUpdate,
    AssetVersionUploadResponse,
    UploadInfo,
)
from src.core.assets.services import build_original_storage_key, resolve_asset_type
from src.core.auth.models import User
from src.modules.s3 import s3_client

from .crud import asset_crud, version_crud

UPLOAD_URL_EXPIRES = 3600


async def init_upload(
    session: AsyncSession, request: AssetUploadRequest, user: User,
) -> AssetVersionUploadResponse:

    version_id = uuid.uuid4()

    asset = await asset_crud.create(
        session,
        dto=AssetCreate(
            title=request.title,
            description=request.description,
            type_=resolve_asset_type(request.file.mime_type),
        ),
        options=user,
    )

    storage_key = build_original_storage_key(asset_id=asset.id, version_id=version_id)
    version = await version_crud.create(
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
        storage_key=storage_key,
        mime_type=request.file.mime_type,
        expires_in=UPLOAD_URL_EXPIRES,
    )

    await session.commit()

    return AssetVersionUploadResponse(
        asset_id=asset.id,
        version_id=version_id,
        version=version.version,
        status=version.status,
        upload=UploadInfo(url=upload_url, expires_in=UPLOAD_URL_EXPIRES),
    )


async def confirm_upload(
        session: AsyncSession, asset_id: uuid.UUID, version_id: uuid.UUID,
) -> ...:

    if (version := await version_crud.read(session, version_id)) is None:
        ...

    if version.asset_id != asset_id:
        ...

    metadata = await s3_client.get_metadata(version.storage_key)

    checksum = metadata.get("ETag", "").strip()
    updated = await version_crud.update(
        session, version,
        dto=AssetVersionUpdate(
            status=AssetVersionStatus.PROCESSING,
            checksum=checksum,
        ),
    )

    if (asset := await asset_crud.read(session, asset_id)) is None:
        raise ...

    await asset_crud.update(session, asset, dto=AssetUpdate(status=AssetStatus.PROCESSING))

    await session.commit()

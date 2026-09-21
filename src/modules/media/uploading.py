from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.media.config import UploadConfig
from src.core.media.crud import get_or_create_object, get_upload_for_update
from src.core.media.dtos import CreateUploadDTO, UploadInfo, UploadResponse
from src.core.media.models import StoredObject, UploadSession, UploadStatus
from src.core.media.utils import build_upload_storage_key
from src.core.media.validation import (
    is_valid_upload_status_to_complete,
    validate_upload_ownership,
    validate_uploaded_object,
)
from src.modules.s3 import s3_client

upload_config = UploadConfig()


async def create_upload(
    session: AsyncSession,
    dto: CreateUploadDTO,
    *,
    user_id: UUID | None = None,
) -> UploadResponse:
    """"""

    upload_id = uuid4()
    storage_key = build_upload_storage_key(upload_id)

    expires_at = datetime.now(UTC).timestamp() + timedelta(seconds=upload_config.url_expires_in)
    upload = UploadSession(
        id=upload_id,
        storage_key=storage_key,
        filename=dto.filename,
        content_type=dto.content_type,
        size_bytes=dto.size_bytes,
        sha256=dto.sha256,
        uploaded_by=user_id,
        expires_at=expires_at,
    )
    session.add(upload)

    url = await s3_client.create_upload_url(
        storage_key,
        content_type=dto.content_type,
        checksum=dto.sha256,
        expires_in=upload_config.url_expires_in,
    )
    await session.flush()

    info = UploadInfo(url=url, expires_in=upload_config.url_expires_in)
    return UploadResponse(id=upload.id, upload=info)


async def complete_upload(
    session: AsyncSession,
    upload_id: UUID,
    *,
    user_id: UUID | None = None,
) -> StoredObject:
    """Идемпотентный метод для завершения сессии загрузки."""

    if (upload := await get_upload_for_update(session, upload_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload session with ID {upload_id!r} not found.",
        )

    validate_upload_ownership(upload, user_id)

    if is_valid_upload_status_to_complete(upload):
        return upload.object

    obj_meta = await s3_client.get_metadata(upload.storage_key)
    validate_uploaded_object(upload, obj_meta)

    stored_object = await get_or_create_object(session, upload, obj_meta)

    upload.object_id = stored_object.id
    upload.status = UploadStatus.COMPLETED

    await session.flush()

    return stored_object


__all__ = ["complete_upload", "create_upload"]

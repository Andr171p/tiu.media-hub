from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.s3.client import ObjectMeta

from .models import StoredObject, UploadSession


async def get_upload_for_update(session: AsyncSession, upload_id: UUID) -> UploadSession | None:
    stmt = select(UploadSession).where(UploadSession.id == upload_id).with_for_update()
    return await session.scalar(stmt)


async def get_or_create_object(
    session: AsyncSession,
    upload: UploadSession,
    obj_meta: ObjectMeta
) -> StoredObject:
    ...

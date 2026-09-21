from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.s3.client import ObjectMeta

from .models import StoredObject, UploadSession, UploadStatus


async def get_upload_for_update(session: AsyncSession, upload_id: UUID) -> UploadSession | None:
    stmt = select(UploadSession).where(UploadSession.id == upload_id).with_for_update()
    return await session.scalar(stmt)


async def get_or_create_object(
    session: AsyncSession, upload: UploadSession, obj_meta: ObjectMeta,
) -> StoredObject:
    """
    Атомарно создает ``StoredObject`` или возвращает существующий
    на основе уникального сочетания sha256 и size_bytes.
    """

    insert_stmt = (
        insert(StoredObject)
        .values(
            storage_key=upload.storage_key,
            size_bytes=obj_meta.size,
            sha256=upload.sha256,
            content_type=obj_meta.content_type,
        )
        .on_conflict_do_nothing(index_elements=["sha256", "size_bytes"])
        .returning(StoredObject)
    )

    result = await session.execute(insert_stmt)
    obj = result.scalar_one_or_none()

    if obj is None:
        select_stmt = select(StoredObject).where(
            StoredObject.sha256 == upload.sha256,
            StoredObject.size_bytes == obj_meta.size,
        )
        obj = await session.scalar(select_stmt)

    return obj


async def get_object(session: AsyncSession, obj_id: UUID) -> StoredObject | None:
    stmt = select(StoredObject).where(StoredObject.id == obj_id)
    return await session.scalar(stmt)


async def get_user_object(
        session: AsyncSession, obj_id: UUID, user_id: UUID,
) -> StoredObject | None:
    """Получает загруженный объект пользователя."""

    stmt = (
        select(StoredObject)
        .join(UploadSession, UploadSession.object_id == obj_id)
        .where(
            StoredObject.id == obj_id,
            UploadSession.uploaded_by == user_id,
            UploadSession.status == UploadStatus.COMPLETED,
        )
        .limit(1)
    )
    return await session.scalar(stmt)

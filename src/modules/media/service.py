from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.common.exceptions import ConflictError, InvalidDataError, NotFoundError
from src.core.s3 import S3Client, S3NotFoundError

from .config import UploadConfig
from .integrity import stream_object
from .models import StoredObject, UploadSession, UploadStatus
from .schemas import CreateUploadDTO, UploadResponse, UploadTarget

_EXPIRED_UPLOAD_GRACE = timedelta(hours=1)


def _original_key(upload_id: UUID) -> str:
    return f"originals/{upload_id}"


async def create_upload(
    session: AsyncSession,
    s3: S3Client,
    config: UploadConfig,
    dto: CreateUploadDTO,
    *,
    user_id: UUID,
) -> UploadResponse:
    if dto.size_bytes > config.max_file_size:
        raise InvalidDataError(
            "File is too large.",
            details={"maxFileSize": config.max_file_size},
        )

    upload_id = uuid4()
    upload = UploadSession(
        id=upload_id,
        storage_key=_original_key(upload_id),
        filename=dto.filename,
        content_type=dto.content_type,
        size_bytes=dto.size_bytes,
        sha256=dto.sha256,
        uploaded_by=user_id,
        expires_at=datetime.now(UTC) + timedelta(seconds=config.url_expires_in),
    )
    session.add(upload)
    await session.flush()

    presigned = await s3.create_upload_url(
        upload.storage_key,
        content_type=dto.content_type,
        sha256=dto.sha256,
        expires_in=config.url_expires_in,
    )
    target = UploadTarget(url=presigned.url, headers=presigned.headers, expires_in=config.url_expires_in)
    return UploadResponse(id=upload.id, target=target)


async def _get_or_create_object(session: AsyncSession, upload: UploadSession) -> tuple[StoredObject, bool]:
    """Атомарно создаёт объект или возвращает существующий с тем же содержимым."""

    stmt = (
        insert(StoredObject)
        .values(
            storage_key=upload.storage_key,
            size_bytes=upload.size_bytes,
            sha256=upload.sha256,
            content_type=upload.content_type,
            verified_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["sha256", "size_bytes"])
        .returning(StoredObject)
    )
    if (created := (await session.execute(stmt)).scalar_one_or_none()) is not None:
        return created, True

    existing = await session.scalar(
        select(StoredObject).where(
            StoredObject.sha256 == upload.sha256,
            StoredObject.size_bytes == upload.size_bytes,
        ),
    )
    if existing is None:
        raise ConflictError("Concurrent upload of the same content, retry the request.")
    return existing, False


async def complete_upload(
    session: AsyncSession,
    s3: S3Client,
    upload_id: UUID,
    *,
    user_id: UUID,
) -> StoredObject:
    """Идемпотентно подтверждает загрузку: сверяет размер и SHA-256 фактического объекта с заявленными."""

    upload = await session.scalar(
        select(UploadSession).where(UploadSession.id == upload_id).with_for_update(),
    )
    if upload is None or upload.uploaded_by != user_id:
        raise NotFoundError("Upload not found.")

    if upload.status is UploadStatus.COMPLETED and upload.object_id is not None:
        return await session.get_one(StoredObject, upload.object_id)

    if upload.status is UploadStatus.EXPIRED:
        raise ConflictError("Upload has expired, start a new one.")

    try:
        info = await s3.get_info(upload.storage_key)
    except S3NotFoundError:
        raise ConflictError("File has not been uploaded yet.") from None

    # Хранилище уже сверило SHA-256 при записи; если оно не вернуло сумму, считаем сами
    sha256 = info.sha256 or (await stream_object(s3, upload.storage_key)).sha256

    if info.size != upload.size_bytes or sha256 != upload.sha256:
        await s3.delete(upload.storage_key)
        upload.status = UploadStatus.EXPIRED
        await session.flush()
        raise InvalidDataError("Uploaded content does not match the declared size or SHA-256.")

    obj, created = await _get_or_create_object(session, upload)
    if not created:
        # Такое содержимое уже хранится: копия не нужна
        await s3.delete(upload.storage_key)

    upload.status = UploadStatus.COMPLETED
    upload.object_id = obj.id
    await session.flush()

    return obj


async def get_owned_object(session: AsyncSession, object_id: UUID, *, user_id: UUID) -> StoredObject:
    """Объект, который пользователь сам загрузил: чужой объект нельзя присвоить по идентификатору."""

    stmt = (
        select(StoredObject)
        .join(UploadSession, UploadSession.object_id == StoredObject.id)
        .where(
            StoredObject.id == object_id,
            UploadSession.uploaded_by == user_id,
            UploadSession.status == UploadStatus.COMPLETED,
        )
        .limit(1)
    )
    if (obj := await session.scalar(stmt)) is None:
        raise NotFoundError("Uploaded object not found.")
    return obj


async def expire_stale_uploads(session: AsyncSession, s3: S3Client) -> int:
    """Закрывает незавершённые загрузки и удаляет то, что успели положить в хранилище."""

    deadline = datetime.now(UTC) - _EXPIRED_UPLOAD_GRACE
    uploads = (
        await session.scalars(
            select(UploadSession)
            .where(UploadSession.status == UploadStatus.PENDING, UploadSession.expires_at < deadline)
            .limit(500)
            .with_for_update(skip_locked=True),
        )
    ).all()

    if not uploads:
        return 0

    await s3.delete(*(upload.storage_key for upload in uploads))
    for upload in uploads:
        upload.status = UploadStatus.EXPIRED
    await session.flush()

    return len(uploads)


__all__ = ["complete_upload", "create_upload", "expire_stale_uploads", "get_owned_object"]

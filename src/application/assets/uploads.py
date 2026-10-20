"""
Загрузка файлов напрямую в хранилище по presigned URL: API не пропускает через себя содержимое.

1. ``start_upload`` — проверка прав и правил коллекции, ссылка на PUT (или на части multipart).
2. Клиент загружает файл в хранилище.
3. ``complete_upload`` — сверка размера и в одной транзакции создание актива или новой версии.

Версия получает ``id`` загрузки, поэтому повторное подтверждение возвращает уже созданный актив.
"""

from typing import Annotated

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork
from ddf.domain.exceptions import InvalidStateError, InvariantViolationError
from pydantic import Field, PositiveInt, StringConstraints

from src.application.auth import AuthUser
from src.application.collections.access import get_collection_access
from src.application.collections.repositories import CollectionRepository
from src.application.dtos import CamelModel
from src.application.outbox import save_events_to_outbox
from src.application.storage import FileStorage, MediaUrls, UploadedPart
from src.domain.assets import Asset, AssetVersion, StoredFile, Upload
from src.domain.assets import logic as assets
from src.domain.collections import Collection, Permission

from .access import get_asset_access
from .dtos import AssetResponse
from .presenters import present_asset
from .repositories import AssetRepository, AssetVersionRepository, UploadRepository

logger = logging.getLogger(__name__)

UPLOAD_TTL = timedelta(hours=6)
MULTIPART_THRESHOLD = 100 * 1024**2
PART_SIZE = 64 * 1024**2
MAX_PARTS = 10_000

type ContentType = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[\w.+-]+/[\w.+-]+$")
]


class StartUploadDTO(CamelModel):
    """Укажите ``collectionId`` для нового актива или ``assetId`` для новой версии."""

    collection_id: UUID | None = None
    asset_id: UUID | None = None
    filename: str = Field(min_length=1, max_length=255)
    content_type: ContentType = Field(examples=["image/jpeg"])
    size: PositiveInt = Field(description="Размер файла, байт")


class UploadPartDTO(CamelModel):
    part_number: int
    url: str


class UploadTicket(CamelModel):
    upload_id: UUID
    expires_at: datetime
    url: str | None = Field(description="PUT-ссылка для файла целиком (если не multipart)")
    headers: dict[str, str] = Field(description="Заголовки, которые нужно передать при загрузке")
    part_size: int | None = Field(description="Размер части multipart, байт")
    parts: list[UploadPartDTO] = Field(description="PUT-ссылки частей; ETag каждой части вернуть в complete")


class CompletedPartDTO(CamelModel):
    part_number: PositiveInt
    etag: str


class CompleteUploadDTO(CamelModel):
    parts: list[CompletedPartDTO] = Field(default_factory=list, description="Только для multipart")
    title: str | None = Field(default=None, max_length=500, description="Название нового актива")
    note: str | None = Field(default=None, max_length=1000, description="Комментарий к новой версии")


def _storage_key(upload_id: UUID, filename: str) -> str:
    now = datetime.now(UTC)
    return f"{now:%Y/%m}/{upload_id}{PurePath(filename).suffix.lower()[:16]}"


def _ensure_allowed(collection: Collection, content_type: str, size: int) -> None:
    if not collection.upload_policy.allows(content_type, size):
        raise InvariantViolationError(
            f"Collection does not accept {content_type} files of {size} bytes.",
            details={"uploadPolicy": sorted(collection.upload_policy.allowed_types)},
        )


async def start_upload(
    dto: StartUploadDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    upload_repository: UploadRepository,
    originals: FileStorage,
    uow: UnitOfWork,
) -> UploadTicket:
    if (dto.collection_id is None) == (dto.asset_id is None):
        raise InvariantViolationError("Specify either collectionId or assetId.")

    if dto.asset_id is not None:
        access = await get_asset_access(
            dto.asset_id,
            auth,
            Permission.WRITE,
            asset_repository=asset_repository,
            collection_repository=collection_repository,
        )
        collection = access.collection
        if not access.asset.accepts(dto.content_type):
            raise InvariantViolationError(f"New version must be {access.asset.kind} like the asset.")
    else:
        assert dto.collection_id is not None
        collection = (
            await get_collection_access(
                dto.collection_id, auth, Permission.WRITE, collection_repository=collection_repository
            )
        ).collection

    _ensure_allowed(collection, dto.content_type, dto.size)

    upload_id = uuid.uuid7()
    file = StoredFile(
        key=_storage_key(upload_id, dto.filename),
        name=dto.filename,
        content_type=dto.content_type,
        size=dto.size,
    )
    expires_in = int(UPLOAD_TTL.total_seconds())
    upload = Upload(
        id=upload_id,
        collection_id=collection.id,
        created_by=auth.user_id,
        file=file,
        asset_id=dto.asset_id,
        expires_at=datetime.now(UTC) + UPLOAD_TTL,
    )

    if dto.size <= MULTIPART_THRESHOLD:
        url = await originals.create_upload_url(file.key, file.content_type, expires_in=expires_in)
        part_size, parts = None, []
    else:
        part_size = max(PART_SIZE, math.ceil(dto.size / MAX_PARTS))
        upload.multipart_id = await originals.start_multipart_upload(file.key, file.content_type)
        urls = await originals.create_part_upload_urls(
            file.key, upload.multipart_id, parts=math.ceil(dto.size / part_size), expires_in=expires_in
        )
        url, parts = None, [UploadPartDTO(part_number=i, url=part_url) for i, part_url in enumerate(urls, 1)]

    await upload_repository.create(upload)
    await uow.commit()

    return UploadTicket(
        upload_id=upload.id,
        expires_at=upload.expires_at,
        url=url,
        headers={"Content-Type": file.content_type} if url else {},
        part_size=part_size,
        parts=parts,
    )


async def complete_upload(
    upload_id: UUID,
    dto: CompleteUploadDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    upload_repository: UploadRepository,
    originals: FileStorage,
    media_urls: MediaUrls,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> AssetResponse:
    upload = await upload_repository.read(upload_id)

    if upload is None or upload.created_by != auth.user_id:
        # Повторное подтверждение: версия уже создана из этой загрузки
        if (version := await version_repository.read(upload_id)) is not None:
            return await _present(
                version,
                auth,
                asset_repository=asset_repository,
                collection_repository=collection_repository,
                media_urls=media_urls,
            )
        raise NotFoundError(f"Upload with ID {upload_id} not found.")

    if upload.is_expired(datetime.now(UTC)):
        raise InvalidStateError("Upload has expired.")

    if upload.multipart_id is not None:
        await originals.complete_multipart_upload(
            upload.file.key,
            upload.multipart_id,
            [UploadedPart(number=part.part_number, etag=part.etag) for part in dto.parts],
        )

    size = await originals.get_size(upload.file.key)
    if size is None:
        raise InvalidStateError("File has not been uploaded yet.")
    if size != upload.file.size:
        raise InvariantViolationError(f"Uploaded {size} bytes instead of declared {upload.file.size}.")

    asset, version = await _register(
        upload,
        dto,
        auth,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )

    if version.number == 1:
        await asset_repository.create(asset)
    else:
        await asset_repository.update(asset)
    await version_repository.create(version)
    await upload_repository.delete(upload.id)
    await save_events_to_outbox(outbox, asset)
    await uow.commit()

    return await _present(
        version,
        auth,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
        media_urls=media_urls,
    )


async def _register(
    upload: Upload,
    dto: CompleteUploadDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
) -> tuple[Asset, AssetVersion]:
    if upload.asset_id is not None:
        access = await get_asset_access(
            upload.asset_id,
            auth,
            Permission.WRITE,
            asset_repository=asset_repository,
            collection_repository=collection_repository,
            with_lock=True,
        )
        version = access.asset.add_version(
            upload.file, created_by=auth.user_id, note=dto.note, version_id=upload.id
        )
        return access.asset, version

    collection = (
        await get_collection_access(
            upload.collection_id, auth, Permission.WRITE, collection_repository=collection_repository
        )
    ).collection
    return assets.create_asset(
        collection, upload.file, created_by=auth.user_id, title=dto.title, version_id=upload.id
    )


async def _present(
    version: AssetVersion,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    media_urls: MediaUrls,
) -> AssetResponse:
    access = await get_asset_access(
        version.asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    return present_asset(access.asset, version, media_urls, permissions=access.permissions)


async def abort_upload(
    upload_id: UUID,
    auth: AuthUser,
    *,
    upload_repository: UploadRepository,
    originals: FileStorage,
    uow: UnitOfWork,
) -> None:
    upload = await upload_repository.read(upload_id)
    if upload is None or upload.created_by != auth.user_id:
        raise NotFoundError(f"Upload with ID {upload_id} not found.")

    await _discard(upload, originals=originals)
    await upload_repository.delete(upload.id)
    await uow.commit()


async def cleanup_expired_uploads(
    *, upload_repository: UploadRepository, originals: FileStorage, uow: UnitOfWork, batch_size: int = 100
) -> int:
    """Удаляет брошенные загрузки и их файлы (планировщик)."""

    expired = await upload_repository.find_expired(datetime.now(UTC), limit=batch_size)

    for upload in expired:
        await _discard(upload, originals=originals)
        await upload_repository.delete(upload.id)

    await uow.commit()
    return len(expired)


async def _discard(upload: Upload, *, originals: FileStorage) -> None:
    try:
        if upload.multipart_id is not None:
            await originals.abort_multipart_upload(upload.file.key, upload.multipart_id)
        await originals.delete_many([upload.file.key])
    except Exception:
        logger.exception("Failed to discard files of upload %s", upload.id)

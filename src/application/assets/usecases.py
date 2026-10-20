import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from ddf.application.dtos import CursorPagination
from ddf.application.exceptions import NotFoundError
from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork
from ddf.domain.exceptions import InvalidStateError
from ddf.domain.utils import apply_changes

from src.application.auth import AuthUser
from src.application.collections.access import get_collection_access, readable_collection_ids
from src.application.collections.repositories import CollectionRepository
from src.application.dtos import CamelModel, CursorPage
from src.application.outbox import save_events_to_outbox
from src.application.processing.repositories import TranscriptRepository
from src.application.storage import FileStorage, MediaUrls
from src.domain.assets import Asset, AssetPurged, AssetVersion
from src.domain.assets import logic as assets
from src.domain.collections import Permission

from .access import get_asset_access
from .dtos import (
    AssetListQuery,
    AssetResponse,
    AssetSummary,
    DownloadResponse,
    MoveAssetDTO,
    UpdateAssetDTO,
    VersionResponse,
)
from .presenters import present_asset, present_summaries, present_version
from .repositories import AssetFilter, AssetQueryRepository, AssetRepository, AssetVersionRepository

logger = logging.getLogger(__name__)

DOWNLOAD_URL_TTL = 15 * 60
TRASH_RETENTION = timedelta(days=30)


async def _read_version(
    asset: Asset, version_id: UUID | None, *, version_repository: AssetVersionRepository
) -> AssetVersion:
    version_id = version_id or asset.current_version_id
    version = await version_repository.read(version_id)

    if version is None or version.asset_id != asset.id:
        raise NotFoundError(f"Version with ID {version_id} not found.")

    return version


async def list_assets(
    query: AssetListQuery,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    asset_query_repository: AssetQueryRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> CursorPage[AssetSummary]:
    if query.collection_id is not None:
        await get_collection_access(query.collection_id, auth, collection_repository=collection_repository)
        collection_ids: list[UUID] | None = [query.collection_id]
    else:
        collection_ids = await readable_collection_ids(auth, collection_repository=collection_repository)

    page = await asset_query_repository.find(
        AssetFilter(
            collection_ids=collection_ids,
            kinds=query.kinds,
            tags=assets.normalize_tags(query.tags),
            person_id=query.person_id,
            created_by=query.created_by,
            license=query.license,
            trashed=query.trashed,
        ),
        CursorPagination(cursor=query.cursor, size=query.size),
        sort=query.sort,
    )
    items = await present_summaries(page.items, version_repository=version_repository, media_urls=media_urls)
    return CursorPage[AssetSummary].build(page, items)


async def get_asset(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> AssetResponse:
    access = await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    version = await _read_version(access.asset, None, version_repository=version_repository)
    return present_asset(access.asset, version, media_urls, permissions=access.permissions)


async def update_asset(
    asset_id: UUID,
    dto: UpdateAssetDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
    uow: UnitOfWork,
) -> AssetResponse:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    asset = access.asset

    if asset.is_deleted:
        raise InvalidStateError("Restore the asset from trash before editing.")

    apply_changes(
        asset,
        title=dto.title,
        tags=assets.normalize_tags(dto.tags) if dto.tags is not None else None,
        metadata=(
            assets.validate_metadata(access.collection.metadata_schema, dto.metadata)
            if dto.metadata is not None
            else None
        ),
    )
    # Явный null очищает необязательные поля
    if "description" in dto.model_fields_set:
        asset.description = dto.description
    if "license" in dto.model_fields_set:
        asset.license = dto.license.to_domain() if dto.license else None

    asset.updated_at = datetime.now(UTC)
    await asset_repository.update(asset)
    await uow.commit()

    version = await _read_version(asset, None, version_repository=version_repository)
    return present_asset(asset, version, media_urls, permissions=access.permissions)


async def move_asset(
    asset_id: UUID,
    dto: MoveAssetDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    target = await get_collection_access(
        dto.collection_id, auth, Permission.WRITE, collection_repository=collection_repository
    )

    assets.move_asset(access.asset, target.collection)

    await asset_repository.update(access.asset)
    await save_events_to_outbox(outbox, access.asset)
    await uow.commit()


async def trash_asset(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    assets.trash_asset(access.asset)

    await asset_repository.update(access.asset)
    await save_events_to_outbox(outbox, access.asset)
    await uow.commit()


async def restore_asset(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    assets.restore_asset(access.asset)

    await asset_repository.update(access.asset)
    await save_events_to_outbox(outbox, access.asset)
    await uow.commit()


async def _purge(
    asset: Asset,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    renditions: FileStorage,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    versions = await version_repository.list_by_asset(asset.id)

    asset.register_event(AssetPurged(asset_id=asset.id))
    await save_events_to_outbox(outbox, asset)
    await asset_repository.delete(asset.id)
    await uow.commit()

    # Файлы удаляются после фиксации: в худшем случае останутся «осиротевшие» объекты, но не битые ссылки
    try:
        await originals.delete_many([version.file.key for version in versions])
        await renditions.delete_many(
            [rendition.file.key for version in versions for rendition in version.renditions]
        )
    except Exception:
        logger.exception("Failed to delete files of purged asset %s", asset.id)


async def purge_asset(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    renditions: FileStorage,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    """Окончательное удаление из корзины."""

    access = await get_asset_access(
        asset_id,
        auth,
        Permission.MANAGE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if not access.asset.is_deleted:
        raise InvalidStateError("Only trashed assets can be purged.")

    await _purge(
        access.asset,
        asset_repository=asset_repository,
        version_repository=version_repository,
        originals=originals,
        renditions=renditions,
        outbox=outbox,
        uow=uow,
    )


async def purge_expired_trash(
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    renditions: FileStorage,
    outbox: OutboxStore,
    uow: UnitOfWork,
    batch_size: int = 100,
) -> int:
    """Удаляет активы, пролежавшие в корзине дольше ``TRASH_RETENTION`` (планировщик)."""

    expired = await asset_repository.find_trashed_before(
        datetime.now(UTC) - TRASH_RETENTION, limit=batch_size
    )

    for asset in expired:
        await _purge(
            asset,
            asset_repository=asset_repository,
            version_repository=version_repository,
            originals=originals,
            renditions=renditions,
            outbox=outbox,
            uow=uow,
        )

    return len(expired)


async def list_versions(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> list[VersionResponse]:
    await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    versions = await version_repository.list_by_asset(asset_id)
    return [present_version(version, media_urls) for version in versions]


async def make_version_current(
    asset_id: UUID,
    version_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
        with_lock=True,
    )
    version = await _read_version(access.asset, version_id, version_repository=version_repository)
    access.asset.make_current(version)

    await asset_repository.update(access.asset)
    await save_events_to_outbox(outbox, access.asset)
    await uow.commit()


class TranscriptSegmentDTO(CamelModel):
    start: float
    end: float
    text: str


class TranscriptResponse(CamelModel):
    language: str | None
    segments: list[TranscriptSegmentDTO]


async def get_transcript(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    transcript_repository: TranscriptRepository,
) -> TranscriptResponse:
    """Расшифровка речи текущей версии: субтитры и переход к моменту в плеере."""

    access = await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    transcript = await transcript_repository.get(access.asset.current_version_id)
    if transcript is None:
        raise NotFoundError("Transcript is not ready or the asset has no speech.")

    return TranscriptResponse.model_validate(transcript)


async def get_asset_for_service(
    asset_id: UUID,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    media_urls: MediaUrls,
) -> ServiceAssetResponse:
    """Доверенный сервис (роль ``assets:read``) читает любой актив вне корзины."""

    asset = await asset_repository.read(asset_id)
    if asset is None or asset.is_deleted:
        raise NotFoundError(f"Asset with ID {asset_id} not found.")

    version = await _read_version(asset, None, version_repository=version_repository)
    url = await originals.create_download_url(
        version.file.key, filename=version.file.name, expires_in=DOWNLOAD_URL_TTL
    )
    return ServiceAssetResponse(
        asset=present_asset(asset, version, media_urls, permissions=[Permission.READ]),
        download=DownloadResponse(url=url, expires_in=DOWNLOAD_URL_TTL),
    )


class ServiceAssetResponse(CamelModel):
    asset: AssetResponse
    download: DownloadResponse


async def get_download_url(
    asset_id: UUID,
    version_id: UUID | None,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
) -> DownloadResponse:
    """Временная ссылка на оригинал: файл скачивается напрямую из хранилища, минуя API."""

    access = await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    version = await _read_version(access.asset, version_id, version_repository=version_repository)
    url = await originals.create_download_url(
        version.file.key, filename=version.file.name, expires_in=DOWNLOAD_URL_TTL
    )
    return DownloadResponse(url=url, expires_in=DOWNLOAD_URL_TTL)

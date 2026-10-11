from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import PermissionDeniedError
from src.core.cdn import CdnClient
from src.core.common.exceptions import ConflictError, InvalidDataError, NotFoundError
from src.core.s3 import S3Client
from src.modules.collections import Action
from src.modules.media import UploadConfig, get_owned_object

from .meta import kind_of
from .models import Asset, AssetStatus, AssetVersion, RenditionKind, VersionStatus
from .queries import VERSION_OPTIONS
from .schemas import CreateVersionDTO, DownloadResponse
from .service import AssetContext, check_upload_policy


async def list_versions(session: AsyncSession, context: AssetContext) -> Sequence[AssetVersion]:
    stmt = (
        select(AssetVersion)
        .where(AssetVersion.asset_id == context.asset.id)
        .order_by(AssetVersion.number.desc())
        .options(*VERSION_OPTIONS)
    )
    return (await session.scalars(stmt)).all()


async def get_asset_version(session: AsyncSession, asset_id: UUID, version_id: UUID) -> AssetVersion:
    version = await session.scalar(
        select(AssetVersion)
        .where(AssetVersion.id == version_id, AssetVersion.asset_id == asset_id)
        .options(*VERSION_OPTIONS)
        .execution_options(populate_existing=True),
    )
    if version is None:
        raise NotFoundError("Version not found.")
    return version


async def get_version(session: AsyncSession, context: AssetContext, version_id: UUID) -> AssetVersion:
    return await get_asset_version(session, context.asset.id, version_id)


async def reset_for_reprocessing(session: AsyncSession, version_id: UUID) -> AssetVersion:
    """Возвращает неуспешную версию в очередь: например, после исправления политики коллекции."""

    version = await session.get(AssetVersion, version_id, with_for_update=True)
    if version is None:
        raise NotFoundError("Version not found.")
    if version.status is not VersionStatus.FAILED:
        raise ConflictError("Only a failed version can be reprocessed.")

    version.status = VersionStatus.PROCESSING
    version.attempts = 0
    version.error = None
    await session.flush()
    return version


async def add_version(session: AsyncSession, context: AssetContext, dto: CreateVersionDTO) -> AssetVersion:
    """Новая версия файла. Текущей она станет после успешной обработки."""

    context.require_edit()
    asset = context.asset

    if asset.status is AssetStatus.ARCHIVED:
        raise ConflictError("Archived asset cannot receive new versions.")

    obj = await get_owned_object(session, dto.object_id, user_id=context.user.user.id)
    check_upload_policy(context.access.collection.settings.upload, obj)

    if dto.source_version_id is not None:
        await get_version(session, context, dto.source_version_id)

    # Блокировка актива сериализует нумерацию версий
    await session.execute(select(Asset.id).where(Asset.id == asset.id).with_for_update())

    duplicate = await session.scalar(
        select(AssetVersion.number).where(
            AssetVersion.asset_id == asset.id, AssetVersion.object_id == obj.id
        ),
    )
    if duplicate is not None:
        raise ConflictError(f"This file is already version {duplicate}.", details={"version": duplicate})

    last_number = await session.scalar(
        select(func.coalesce(func.max(AssetVersion.number), 0)).where(AssetVersion.asset_id == asset.id),
    )
    version = AssetVersion(
        asset_id=asset.id,
        number=(last_number or 0) + 1,
        object_id=obj.id,
        original_filename=dto.original_filename,
        created_by=context.user.user.id,
        source_version_id=dto.source_version_id,
    )
    session.add(version)
    await session.flush()
    return version


async def promote_version(session: AsyncSession, context: AssetContext, version_id: UUID) -> None:
    """Делает готовую версию текущей: откат к предыдущей или возврат к новой."""

    context.require_edit()
    version = await get_version(session, context, version_id)

    if version.status is not VersionStatus.READY:
        raise InvalidDataError("Only a processed version can become current.")

    context.asset.current_version_id = version.id
    if version.meta is not None:
        context.asset.kind = kind_of(version.meta.mime_type)
    await session.flush()


async def create_download(
    context: AssetContext,
    version: AssetVersion,
    *,
    s3: S3Client,
    cdn: CdnClient,
    config: UploadConfig,
) -> DownloadResponse:
    """Оригинал скачивают участники коллекции, остальные получают превью с водяным знаком."""

    if context.access.can(Action.CONTRIBUTE):
        url = await s3.create_download_url(
            version.object.storage_key,
            filename=version.original_filename,
            expires_in=config.download_url_expires_in,
        )
        return DownloadResponse(url=url, filename=version.original_filename, kind="original")

    preview = next((item for item in version.renditions if item.kind is RenditionKind.PREVIEW), None)
    if preview is None:
        raise PermissionDeniedError("Original file is available to collection members only.")

    return DownloadResponse(
        url=cdn.url(preview.storage_key),
        filename=f"{version.original_filename}.webp",
        kind="preview",
    )


__all__ = [
    "add_version",
    "create_download",
    "get_asset_version",
    "get_version",
    "list_versions",
    "promote_version",
    "reset_for_reprocessing",
]

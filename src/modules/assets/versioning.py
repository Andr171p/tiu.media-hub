from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.dtos import CreateAssetVersionDTO
from src.core.assets.models import (
    Asset,
    AssetVersion,
    Object,
    UploadSession,
    UploadStatus,
    VersionStatus,
)
from src.core.common.shortcuts import get_or_raise_404


async def get_asset_version_by_upload(
    session: AsyncSession,
    asset_id: UUID,
    upload_id: UUID,
) -> AssetVersion | None:
    """Получает версию по её идентификатору загрузочной сессии."""

    stmt = select(AssetVersion).where(
        (AssetVersion.asset_id == asset_id)
        & (AssetVersion.upload_id == upload_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_upload_for_update(
    session: AsyncSession,
    asset_id: UUID,
    upload_id: UUID,
) -> UploadSession:
    """Получает и блокирует загрузочную сессию указанного Asset."""

    stmt = (
        select(UploadSession)
        .where(
            UploadSession.id == upload_id,
            UploadSession.asset_id == asset_id,
            UploadSession.deleted_at.is_(None),
        )
        .with_for_update()
    )

    if (upload := await session.scalar(stmt)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UploadSession with ID {upload_id!r} not found.",
        )

    return upload


async def _get_next_version_number(session: AsyncSession, asset_id: UUID) -> int:
    """Получает следующий порядковый номер версии."""

    stmt = (
        select(func.coalesce(func.max(AssetVersion.number), 0))
        .where(AssetVersion.asset_id == asset_id)
    )
    current = await session.scalar(stmt) or 0
    return current + 1


def _set_object_meta(obj: Object, dto: CreateAssetVersionDTO) -> None:
    obj.mime_type = dto.mime_type
    obj.size_bytes = dto.size
    obj.checksum = dto.checksum


def _set_version_meta(version: AssetVersion, dto: CreateAssetVersionDTO) -> None:
    version.meta = dto.meta
    version.raw_meta = dto.raw_meta


def _validate_object_meta(obj: Object, dto: CreateAssetVersionDTO) -> None:
    """Проверяет, что повторный запрос относится к тому же физическому объекту."""

    if (
        obj.mime_type != dto.mime_type
        or obj.size_bytes != dto.size
        or obj.checksum != dto.checksum
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source object metadata does not match the accepted version.",
        )


async def sync_asset_version(
    session: AsyncSession,
    asset_id: UUID,
    upload_id: UUID,
    dto: CreateAssetVersionDTO,
) -> AssetVersion:
    """Идемпотентный метод для синхронизации версии из загрузочной сессии."""

    upload = await get_or_raise_404(session, UploadSession, upload_id)
    existing = await get_asset_version_by_upload(session, asset_id, upload_id)

    if existing is not None:
        obj = await get_or_raise_404(session, Object, existing.object_id, for_update=True)

        _validate_object_meta(obj, dto)

        if existing.status == VersionStatus.PROCESSING:
            _set_version_meta(existing, dto)
            await session.flush()

        return existing

    if upload.status != UploadStatus.VALIDATING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Asset version can only be created from a validating "
                f"upload session, got {upload.status.value!r}."
            ),
        )

    asset = await get_or_raise_404(session, Asset, asset_id, for_update=True)
    obj = await get_or_raise_404(session, Object, upload.object_id, for_update=True)

    _set_object_meta(obj, dto)

    next_number = await _get_next_version_number(session, asset_id)
    version = AssetVersion(
        asset_id=asset.id,
        upload_id=upload.id,
        object_id=obj.id,
        number=next_number,
        original_filename=upload.filename,
        meta=dto.meta,
        raw_meta=dto.raw_meta,
    )
    session.add(version)

    upload.status = UploadStatus.COMPLETED
    await session.flush()

    return version


__all__ = ["sync_asset_version"]

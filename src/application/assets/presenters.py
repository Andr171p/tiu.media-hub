"""Сборка ответов API: единственное место, где ключи производных превращаются в ссылки CDN."""

from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

from src.application.storage import MediaUrls
from src.domain.assets import Asset, AssetVersion, License, RenditionKind
from src.domain.collections import Permission

from .dtos import (
    AssetResponse,
    AssetSummary,
    FileDTO,
    LicenseResponse,
    PeriodDTO,
    ProcessingStatus,
    RenditionUrls,
    VersionMetaDTO,
    VersionResponse,
)
from .repositories import AssetVersionRepository


def _status(version: AssetVersion) -> ProcessingStatus:
    if version.processed_at is None:
        return ProcessingStatus.PROCESSING

    return ProcessingStatus.FAILED if version.processing_error else ProcessingStatus.READY


def _present_license(license_: License, today: date) -> LicenseResponse:
    return LicenseResponse(
        type=license_.type,
        holder=license_.holder,
        period=PeriodDTO(start=license_.period.start, end=license_.period.end),
        territories=sorted(license_.territories),
        channels=sorted(license_.channels),
        restrictions=license_.restrictions,
        status=license_.status(today),
    )


def present_version(version: AssetVersion, media_urls: MediaUrls) -> VersionResponse:
    def url(kind: RenditionKind) -> str | None:
        rendition = version.rendition(kind)
        return media_urls.url(rendition.file.key) if rendition else None

    return VersionResponse(
        id=version.id,
        number=version.number,
        file=FileDTO.model_validate(version.file),
        status=_status(version),
        processing_error=version.processing_error,
        meta=VersionMetaDTO.model_validate(version.meta) if version.meta else None,
        urls=RenditionUrls(
            thumbnail=url(RenditionKind.THUMBNAIL),
            preview=url(RenditionKind.PREVIEW),
            video=url(RenditionKind.VIDEO),
            audio=url(RenditionKind.AUDIO),
        ),
        source_version_id=version.source_version_id,
        note=version.note,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def present_summary(asset: Asset, version: AssetVersion, media_urls: MediaUrls) -> AssetSummary:
    today = datetime.now(UTC).date()

    return AssetSummary(
        id=asset.id,
        collection_id=asset.collection_id,
        title=asset.title,
        kind=asset.kind,
        tags=list(asset.tags),
        license_status=asset.license.status(today) if asset.license else None,
        created_by=asset.created_by,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        trashed_at=asset.deleted_at,
        version=present_version(version, media_urls),
    )


def present_asset(
    asset: Asset,
    version: AssetVersion,
    media_urls: MediaUrls,
    *,
    permissions: Iterable[Permission],
) -> AssetResponse:
    today = datetime.now(UTC).date()
    summary = present_summary(asset, version, media_urls)

    return AssetResponse(
        **dict(summary),
        description=asset.description,
        caption=asset.caption,
        metadata=asset.metadata,
        license=_present_license(asset.license, today) if asset.license else None,
        version_count=asset.version_count,
        permissions=sorted(permissions),
    )


async def present_summaries(
    assets: Sequence[Asset], *, version_repository: AssetVersionRepository, media_urls: MediaUrls
) -> list[AssetSummary]:
    """Карточки активов с текущими версиями (один запрос за версиями)."""

    versions = await version_repository.get_by_ids([asset.current_version_id for asset in assets])
    by_id = {version.id: version for version in versions}

    return [
        present_summary(asset, by_id[asset.current_version_id], media_urls)
        for asset in assets
        if asset.current_version_id in by_id
    ]


__all__ = ["present_asset", "present_summaries", "present_summary", "present_version"]

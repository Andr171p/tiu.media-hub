from datetime import UTC, datetime

from src.core.cdn import CdnClient
from src.modules.collections import CollectionSettings
from src.modules.users import UserResponse

from .compliance import evaluate_compliance
from .models import Asset, AssetVersion, RenditionKind
from .schemas import AssetResponse, AssetTagResponse, Renditions, VersionResponse


def to_version_response(version: AssetVersion, cdn: CdnClient, *, is_current: bool) -> VersionResponse:
    urls = {rendition.kind: cdn.url(rendition.storage_key) for rendition in version.renditions}

    return VersionResponse(
        id=version.id,
        number=version.number,
        status=version.status,
        error=version.error,
        original_filename=version.original_filename,
        size_bytes=version.object.size_bytes,
        sha256=version.object.sha256,
        content_type=version.meta.mime_type if version.meta else version.object.content_type,
        meta=version.meta,
        issues=version.issues,
        source_version_id=version.source_version_id,
        created_by=UserResponse.model_validate(version.creator),
        created_at=version.created_at,
        processed_at=version.processed_at,
        renditions=Renditions(
            thumbnail=urls.get(RenditionKind.THUMBNAIL),
            preview=urls.get(RenditionKind.PREVIEW),
        ),
        is_current=is_current,
    )


def to_asset_response(
    asset: Asset,
    *,
    cdn: CdnClient,
    settings: CollectionSettings,
    can_edit: bool,
    pending_version: AssetVersion | None = None,
) -> AssetResponse:
    current = asset.current_version
    issues = evaluate_compliance(
        license_=asset.license,
        custom_meta=asset.custom_meta,
        fields=settings.metadata_fields,
        license_policy=settings.license,
        meta=current.meta if current else None,
        today=datetime.now(UTC).date(),
    )
    if current is not None:
        issues = [*current.issues, *issues]

    return AssetResponse(
        id=asset.id,
        collection_id=asset.collection_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        title=asset.title,
        description=asset.description,
        kind=asset.kind,
        status=asset.status,
        author=UserResponse.model_validate(asset.author),
        custom_meta=asset.custom_meta,
        license=asset.license,
        tags=sorted(
            (
                AssetTagResponse(name=item.tag.name, source=item.source, confidence=item.confidence)
                for item in asset.tags
            ),
            key=lambda tag: tag.name,
        ),
        current_version=to_version_response(current, cdn, is_current=True) if current else None,
        pending_version=(
            to_version_response(pending_version, cdn, is_current=False) if pending_version else None
        ),
        issues=issues,
        can_edit=can_edit,
    )


__all__ = ["to_asset_response", "to_version_response"]

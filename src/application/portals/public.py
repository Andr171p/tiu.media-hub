"""
Портал для посетителей. Содержимое собирается при каждом открытии, поэтому всегда актуально.
Скрываются удалённые активы и активы с недействующей лицензией.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from http import HTTPStatus
from uuid import UUID

from ddf.application.dtos import CursorPagination
from ddf.application.exceptions import ApplicationError, NotFoundError

from src.application.assets.dtos import DownloadResponse
from src.application.assets.repositories import (
    AssetFilter,
    AssetQueryRepository,
    AssetRepository,
    AssetVersionRepository,
)
from src.application.assets.usecases import DOWNLOAD_URL_TTL
from src.application.auth import Auth, AuthType, PermissionDeniedError
from src.application.selections import SelectionRepository
from src.application.storage import FileStorage, MediaUrls
from src.domain.assets import Asset, RenditionKind
from src.domain.assets import logic as assets
from src.domain.portals import FilesBlock, GalleryBlock, HeroBlock, Portal, PortalAccess, TextBlock

from .dtos import (
    PortalToken,
    PublicAsset,
    PublicBlock,
    PublicFiles,
    PublicGallery,
    PublicHero,
    PublicPortal,
    PublicText,
    UnlockPortalDTO,
)
from .ports import PortalRepository, PortalSecrets

TOKEN_TTL = 12 * 60 * 60


class PortalLockedError(ApplicationError):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "portal_locked"


@dataclass(frozen=True, slots=True)
class Visitor:
    auth: Auth | None = None
    token: str | None = None


def _is_usable(asset: Asset, today: date) -> bool:
    return not asset.is_deleted and (asset.license is None or asset.license.is_usable(today))


async def _open(
    slug: str, visitor: Visitor, *, portal_repository: PortalRepository, secrets: PortalSecrets
) -> Portal:
    portal = await portal_repository.find_by_slug(slug)
    if portal is None or not portal.is_published:
        raise NotFoundError(f"Portal {slug!r} not found.")

    match portal.access:
        case PortalAccess.EMPLOYEES if visitor.auth is None or visitor.auth.type is not AuthType.USER:
            raise PortalLockedError("Sign in to open this portal.", details={"access": portal.access})
        case PortalAccess.PASSWORD if not (visitor.token and secrets.verify_token(visitor.token, portal.id)):
            raise PortalLockedError("Password required.", details={"access": portal.access})

    return portal


async def unlock_portal(
    slug: str, dto: UnlockPortalDTO, *, portal_repository: PortalRepository, secrets: PortalSecrets
) -> PortalToken:
    portal = await portal_repository.find_by_slug(slug)
    if portal is None or not portal.is_published or portal.access is not PortalAccess.PASSWORD:
        raise NotFoundError(f"Portal {slug!r} not found.")

    if portal.password_hash is None or not secrets.verify_password(dto.password, portal.password_hash):
        raise PermissionDeniedError("Wrong password.")

    return PortalToken(token=secrets.issue_token(portal.id, ttl=TOKEN_TTL), expires_in=TOKEN_TTL)


async def _gallery_assets(
    block: GalleryBlock,
    today: date,
    *,
    asset_repository: AssetRepository,
    asset_query_repository: AssetQueryRepository,
    selection_repository: SelectionRepository,
) -> list[Asset]:
    if block.collection_id is not None:
        page = await asset_query_repository.find(
            AssetFilter(
                collection_ids=[block.collection_id],
                tags=assets.normalize_tags(block.tags),
                usable_on=today,
            ),
            CursorPagination(cursor=None, size=block.limit),
        )
        return list(page.items)

    selection = await selection_repository.read(block.selection_id) if block.selection_id else None
    if selection is None:
        return []

    found = {asset.id: asset for asset in await asset_repository.get_by_ids(selection.asset_ids)}
    tags = set(assets.normalize_tags(block.tags))

    return [
        asset
        for asset_id in selection.asset_ids
        if (asset := found.get(asset_id)) and _is_usable(asset, today) and tags <= set(asset.tags)
    ][: block.limit]


async def _present_assets(
    items: Sequence[Asset], *, version_repository: AssetVersionRepository, media_urls: MediaUrls
) -> dict[UUID, PublicAsset]:
    versions = {
        version.id: version
        for version in await version_repository.get_by_ids([asset.current_version_id for asset in items])
    }
    result: dict[UUID, PublicAsset] = {}

    for asset in items:
        if (version := versions.get(asset.current_version_id)) is None:
            continue

        def url(kind: RenditionKind) -> str | None:
            rendition = version.rendition(kind)
            return media_urls.url(rendition.file.key) if rendition else None

        result[asset.id] = PublicAsset(
            id=asset.id,
            title=asset.title,
            description=asset.description,
            kind=asset.kind,
            width=version.meta.width if version.meta else None,
            height=version.meta.height if version.meta else None,
            duration=version.meta.duration if version.meta else None,
            thumbnail_url=url(RenditionKind.THUMBNAIL),
            preview_url=url(RenditionKind.PREVIEW),
            video_url=url(RenditionKind.VIDEO),
            audio_url=url(RenditionKind.AUDIO),
            file_name=version.file.name,
            file_size=version.file.size,
        )

    return result


async def view_portal(
    slug: str,
    visitor: Visitor,
    *,
    portal_repository: PortalRepository,
    secrets: PortalSecrets,
    asset_repository: AssetRepository,
    asset_query_repository: AssetQueryRepository,
    selection_repository: SelectionRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> PublicPortal:
    portal = await _open(slug, visitor, portal_repository=portal_repository, secrets=secrets)
    today = datetime.now(UTC).date()

    galleries = {
        index: await _gallery_assets(
            block,
            today,
            asset_repository=asset_repository,
            asset_query_repository=asset_query_repository,
            selection_repository=selection_repository,
        )
        for index, block in enumerate(portal.blocks)
        if isinstance(block, GalleryBlock)
    }
    direct = [
        asset
        for asset in await asset_repository.get_by_ids(list(portal.sources().asset_ids))
        if _is_usable(asset, today)
    ]
    public = await _present_assets(
        [*direct, *(asset for items in galleries.values() for asset in items)],
        version_repository=version_repository,
        media_urls=media_urls,
    )

    def pick(asset_id: UUID | None) -> PublicAsset | None:
        return public.get(asset_id) if asset_id else None

    blocks: list[PublicBlock] = []
    for index, block in enumerate(portal.blocks):
        match block:
            case HeroBlock():
                blocks.append(
                    PublicHero(title=block.title, subtitle=block.subtitle, image=pick(block.image_asset_id))
                )
            case TextBlock():
                blocks.append(PublicText(markdown=block.markdown))
            case GalleryBlock():
                items = [public[asset.id] for asset in galleries[index] if asset.id in public]
                blocks.append(PublicGallery(title=block.title, items=items))
            case FilesBlock():
                items = [public[asset_id] for asset_id in block.asset_ids if asset_id in public]
                blocks.append(PublicFiles(title=block.title, items=items))

    return PublicPortal(
        slug=portal.slug,
        title=portal.title,
        description=portal.description,
        accent_color=portal.theme.accent_color,
        logo=pick(portal.theme.logo_asset_id),
        cover=pick(portal.theme.cover_asset_id),
        blocks=blocks,
        allow_download=portal.allow_download,
    )


async def _belongs_to_portal(
    portal: Portal, asset: Asset, *, selection_repository: SelectionRepository
) -> bool:
    sources = portal.sources()

    if asset.id in sources.asset_ids:
        return True

    for block in portal.blocks:
        if not isinstance(block, GalleryBlock) or not set(assets.normalize_tags(block.tags)) <= set(
            asset.tags
        ):
            continue
        if block.collection_id == asset.collection_id:
            return True
        selection = await selection_repository.read(block.selection_id) if block.selection_id else None
        if selection is not None and asset.id in selection.asset_ids:
            return True

    return False


async def download_from_portal(
    slug: str,
    asset_id: UUID,
    visitor: Visitor,
    *,
    portal_repository: PortalRepository,
    secrets: PortalSecrets,
    asset_repository: AssetRepository,
    selection_repository: SelectionRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
) -> DownloadResponse:
    portal = await _open(slug, visitor, portal_repository=portal_repository, secrets=secrets)
    asset = await asset_repository.read(asset_id)

    if (
        not portal.allow_download
        or asset is None
        or not _is_usable(asset, datetime.now(UTC).date())
        or not await _belongs_to_portal(portal, asset, selection_repository=selection_repository)
    ):
        raise NotFoundError(f"Asset with ID {asset_id} not found.")

    version = await version_repository.read(asset.current_version_id)
    if version is None:
        raise NotFoundError(f"Asset with ID {asset_id} not found.")

    url = await originals.create_download_url(
        version.file.key, filename=version.file.name, expires_in=DOWNLOAD_URL_TTL
    )
    return DownloadResponse(url=url, expires_in=DOWNLOAD_URL_TTL)

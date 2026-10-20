from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Header

from src.api.dependencies.auth import OptionalAuth
from src.api.dependencies.repositories import (
    AssetQueryRepositoryDep,
    AssetRepositoryDep,
    PortalRepositoryDep,
    SelectionRepositoryDep,
    VersionRepositoryDep,
)
from src.api.dependencies.services import MediaUrlsDep, OriginalsDep, PortalSecretsDep
from src.application.assets.dtos import DownloadResponse
from src.application.portals import public
from src.application.portals.dtos import PortalToken, PublicPortal, UnlockPortalDTO

router = APIRouter(prefix="/portals", tags=["Публичные порталы"])

type PortalTokenHeader = Annotated[str | None, Header(alias="X-Portal-Token")]


@router.get(
    "/{slug}",
    summary="Открыть портал",
    description=(
        "Без авторизации для public; Bearer сотрудника для employees; "
        "X-Portal-Token из /unlock для password. Закрытый портал отвечает 401 portal_locked."
    ),
)
async def view_portal(
    slug: str,
    auth: OptionalAuth,
    portals: PortalRepositoryDep,
    secrets: PortalSecretsDep,
    assets: AssetRepositoryDep,
    asset_queries: AssetQueryRepositoryDep,
    selections: SelectionRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
    token: PortalTokenHeader = None,
) -> PublicPortal:
    return await public.view_portal(
        slug,
        public.Visitor(auth=auth, token=token),
        portal_repository=portals,
        secrets=secrets,
        asset_repository=assets,
        asset_query_repository=asset_queries,
        selection_repository=selections,
        version_repository=versions,
        media_urls=media_urls,
    )


@router.post("/{slug}/unlock", summary="Войти по паролю")
async def unlock_portal(
    slug: str, dto: UnlockPortalDTO, portals: PortalRepositoryDep, secrets: PortalSecretsDep
) -> PortalToken:
    return await public.unlock_portal(slug, dto, portal_repository=portals, secrets=secrets)


@router.get("/{slug}/assets/{asset_id}/download", summary="Скачать оригинал (если разрешено)")
async def download(
    slug: str,
    asset_id: UUID,
    auth: OptionalAuth,
    portals: PortalRepositoryDep,
    secrets: PortalSecretsDep,
    assets: AssetRepositoryDep,
    selections: SelectionRepositoryDep,
    versions: VersionRepositoryDep,
    originals: OriginalsDep,
    token: PortalTokenHeader = None,
) -> DownloadResponse:
    return await public.download_from_portal(
        slug,
        asset_id,
        public.Visitor(auth=auth, token=token),
        portal_repository=portals,
        secrets=secrets,
        asset_repository=assets,
        selection_repository=selections,
        version_repository=versions,
        originals=originals,
    )

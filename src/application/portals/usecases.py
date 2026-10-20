from datetime import UTC, datetime
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.uow import UnitOfWork
from ddf.domain.utils import apply_changes

from src.application.assets.repositories import AssetRepository
from src.application.auth import AuthUser
from src.application.collections.access import get_collection_access
from src.application.collections.repositories import CollectionRepository
from src.application.selections import SelectionRepository, readable_assets
from src.domain.portals import Portal

from .dtos import CreatePortalDTO, PortalResponse, ThemeDTO, UpdatePortalDTO, block_to_dto
from .ports import PortalRepository, PortalSecrets


def present_portal(portal: Portal) -> PortalResponse:
    return PortalResponse(
        id=portal.id,
        slug=portal.slug,
        title=portal.title,
        description=portal.description,
        theme=ThemeDTO.model_validate(portal.theme),
        blocks=[block_to_dto(block) for block in portal.blocks],
        access=portal.access,
        allow_download=portal.allow_download,
        published_at=portal.published_at,
        owner_id=portal.owner_id,
        created_at=portal.created_at,
        updated_at=portal.updated_at,
    )


async def _ensure_sources_readable(
    portal: Portal,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    selection_repository: SelectionRepository,
) -> None:
    """Публикует только тот, кто сам видит содержимое: портал не должен открывать чужие коллекции."""

    sources = portal.sources()

    for collection_id in sources.collection_ids:
        await get_collection_access(collection_id, auth, collection_repository=collection_repository)

    for selection_id in sources.selection_ids:
        selection = await selection_repository.read(selection_id)
        if selection is None or not (selection.shared or selection.owner_id == auth.user_id or auth.is_admin):
            raise NotFoundError(f"Selection with ID {selection_id} not found.")

    readable = await readable_assets(
        list(sources.asset_ids),
        auth,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if missing := sources.asset_ids - {asset.id for asset in readable}:
        raise NotFoundError("Some assets are not available.", details=[str(asset_id) for asset_id in missing])


async def _read_owned(portal_id: UUID, auth: AuthUser, *, portal_repository: PortalRepository) -> Portal:
    portal = await portal_repository.read(portal_id)

    if portal is None or (portal.owner_id != auth.user_id and not auth.is_admin):
        raise NotFoundError(f"Portal with ID {portal_id} not found.")

    return portal


async def create_portal(
    dto: CreatePortalDTO,
    auth: AuthUser,
    *,
    portal_repository: PortalRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    selection_repository: SelectionRepository,
    secrets: PortalSecrets,
    uow: UnitOfWork,
) -> PortalResponse:
    portal = Portal(
        slug=dto.slug,
        title=dto.title,
        description=dto.description,
        owner_id=auth.user_id,
        theme=dto.theme.to_domain(),
        blocks=tuple(block.to_domain() for block in dto.blocks),
        access=dto.access,
        password_hash=secrets.hash_password(dto.password) if dto.password else None,
        allow_download=dto.allow_download,
        published_at=datetime.now(UTC) if dto.published else None,
    )
    await _ensure_sources_readable(
        portal,
        auth,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
        selection_repository=selection_repository,
    )

    await portal_repository.create(portal)
    await uow.commit()

    return present_portal(portal)


async def list_portals(auth: AuthUser, *, portal_repository: PortalRepository) -> list[PortalResponse]:
    portals = await portal_repository.list_owned(None if auth.is_admin else auth.user_id)
    return [present_portal(portal) for portal in portals]


async def get_portal(
    portal_id: UUID, auth: AuthUser, *, portal_repository: PortalRepository
) -> PortalResponse:
    return present_portal(await _read_owned(portal_id, auth, portal_repository=portal_repository))


async def update_portal(
    portal_id: UUID,
    dto: UpdatePortalDTO,
    auth: AuthUser,
    *,
    portal_repository: PortalRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    selection_repository: SelectionRepository,
    secrets: PortalSecrets,
    uow: UnitOfWork,
) -> PortalResponse:
    portal = await _read_owned(portal_id, auth, portal_repository=portal_repository)

    apply_changes(
        portal,
        slug=dto.slug,
        title=dto.title,
        theme=dto.theme.to_domain() if dto.theme else None,
        blocks=tuple(block.to_domain() for block in dto.blocks) if dto.blocks is not None else None,
        allow_download=dto.allow_download,
    )
    if "description" in dto.model_fields_set:
        portal.description = dto.description

    if dto.access is not None or dto.password is not None:
        portal.set_access(
            dto.access or portal.access,
            secrets.hash_password(dto.password) if dto.password else None,
        )

    if dto.published is not None and dto.published != portal.is_published:
        portal.published_at = datetime.now(UTC) if dto.published else None

    if dto.theme is not None or dto.blocks is not None:
        await _ensure_sources_readable(
            portal,
            auth,
            asset_repository=asset_repository,
            collection_repository=collection_repository,
            selection_repository=selection_repository,
        )

    portal.updated_at = datetime.now(UTC)
    await portal_repository.update(portal)
    await uow.commit()

    return present_portal(portal)


async def delete_portal(
    portal_id: UUID, auth: AuthUser, *, portal_repository: PortalRepository, uow: UnitOfWork
) -> None:
    await _read_owned(portal_id, auth, portal_repository=portal_repository)
    await portal_repository.delete(portal_id)
    await uow.commit()


__all__ = [
    "create_portal",
    "delete_portal",
    "get_portal",
    "list_portals",
    "present_portal",
    "update_portal",
]

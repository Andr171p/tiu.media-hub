"""Подборки: списки активов из разных коллекций. Их же показывают галереи порталов."""

from typing import Annotated

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.repositories import Repository
from ddf.application.uow import UnitOfWork
from ddf.domain.utils import apply_changes
from pydantic import Field, StringConstraints

from src.application.assets.dtos import AssetSummary
from src.application.assets.presenters import present_summaries
from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser, PermissionDeniedError
from src.application.collections.access import readable_collection_ids
from src.application.collections.repositories import CollectionRepository
from src.application.dtos import CamelModel
from src.application.storage import MediaUrls
from src.domain.assets import Asset
from src.domain.selections import Selection

type Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class SelectionRepository(Repository[Selection]):
    async def list_visible(self, user_id: UUID | None) -> Sequence[Selection]:
        """Свои и общие подборки; ``None`` — все (администратор)."""
        raise NotImplementedError


class CreateSelectionDTO(CamelModel):
    name: Name
    description: str | None = Field(default=None, max_length=2000)
    shared: bool = Field(default=False, description="Видна всем сотрудникам")
    asset_ids: list[UUID] = Field(default_factory=list)


class UpdateSelectionDTO(CamelModel):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)
    shared: bool | None = None


class SelectionItemsDTO(CamelModel):
    asset_ids: list[UUID] = Field(min_length=1, max_length=1000)


class SelectionResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    shared: bool
    owner_id: UUID
    asset_count: int
    created_at: datetime
    updated_at: datetime


def _present(selection: Selection) -> SelectionResponse:
    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        description=selection.description,
        shared=selection.shared,
        owner_id=selection.owner_id,
        asset_count=len(selection.asset_ids),
        created_at=selection.created_at,
        updated_at=selection.updated_at,
    )


async def _read(
    selection_id: UUID, auth: AuthUser, *, edit: bool, selection_repository: SelectionRepository
) -> Selection:
    selection = await selection_repository.read(selection_id)
    is_owner = selection is not None and (selection.owner_id == auth.user_id or auth.is_admin)

    if selection is None or not (is_owner or selection.shared):
        raise NotFoundError(f"Selection with ID {selection_id} not found.")

    if edit and not is_owner:
        raise PermissionDeniedError("Only the owner can change a selection.")

    return selection


async def readable_assets(
    asset_ids: Sequence[UUID],
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
) -> list[Asset]:
    """Активы в исходном порядке, кроме удалённых и недоступных пользователю."""

    readable = await readable_collection_ids(auth, collection_repository=collection_repository)
    allowed = None if readable is None else set(readable)
    found = {asset.id: asset for asset in await asset_repository.get_by_ids(asset_ids)}

    return [
        asset
        for asset_id in asset_ids
        if (asset := found.get(asset_id)) is not None
        and not asset.is_deleted
        and (allowed is None or asset.collection_id in allowed)
    ]


async def create_selection(
    dto: CreateSelectionDTO,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> SelectionResponse:
    selection = Selection(
        name=dto.name, description=dto.description, shared=dto.shared, owner_id=auth.user_id
    )
    assets = await readable_assets(
        dto.asset_ids, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    selection.add(asset.id for asset in assets)

    await selection_repository.create(selection)
    await uow.commit()

    return _present(selection)


async def list_selections(
    auth: AuthUser, *, selection_repository: SelectionRepository
) -> list[SelectionResponse]:
    selections = await selection_repository.list_visible(None if auth.is_admin else auth.user_id)
    return [_present(selection) for selection in selections]


async def get_selection(
    selection_id: UUID, auth: AuthUser, *, selection_repository: SelectionRepository
) -> SelectionResponse:
    return _present(await _read(selection_id, auth, edit=False, selection_repository=selection_repository))


async def list_selection_assets(
    selection_id: UUID,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> list[AssetSummary]:
    selection = await _read(selection_id, auth, edit=False, selection_repository=selection_repository)
    assets = await readable_assets(
        selection.asset_ids,
        auth,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    return await present_summaries(assets, version_repository=version_repository, media_urls=media_urls)


async def update_selection(
    selection_id: UUID,
    dto: UpdateSelectionDTO,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    uow: UnitOfWork,
) -> SelectionResponse:
    selection = await _read(selection_id, auth, edit=True, selection_repository=selection_repository)

    apply_changes(selection, name=dto.name, shared=dto.shared)
    if "description" in dto.model_fields_set:
        selection.description = dto.description

    await selection_repository.update(selection)
    await uow.commit()

    return _present(selection)


async def delete_selection(
    selection_id: UUID, auth: AuthUser, *, selection_repository: SelectionRepository, uow: UnitOfWork
) -> None:
    await _read(selection_id, auth, edit=True, selection_repository=selection_repository)
    await selection_repository.delete(selection_id)
    await uow.commit()


async def add_selection_assets(
    selection_id: UUID,
    dto: SelectionItemsDTO,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> SelectionResponse:
    selection = await _read(selection_id, auth, edit=True, selection_repository=selection_repository)
    assets = await readable_assets(
        dto.asset_ids, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    selection.add(asset.id for asset in assets)

    await selection_repository.update(selection)
    await uow.commit()

    return _present(selection)


async def remove_selection_assets(
    selection_id: UUID,
    dto: SelectionItemsDTO,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    uow: UnitOfWork,
) -> SelectionResponse:
    selection = await _read(selection_id, auth, edit=True, selection_repository=selection_repository)
    selection.remove(dto.asset_ids)

    await selection_repository.update(selection)
    await uow.commit()

    return _present(selection)


async def reorder_selection(
    selection_id: UUID,
    dto: SelectionItemsDTO,
    auth: AuthUser,
    *,
    selection_repository: SelectionRepository,
    uow: UnitOfWork,
) -> SelectionResponse:
    selection = await _read(selection_id, auth, edit=True, selection_repository=selection_repository)
    selection.reorder(dto.asset_ids)

    await selection_repository.update(selection)
    await uow.commit()

    return _present(selection)

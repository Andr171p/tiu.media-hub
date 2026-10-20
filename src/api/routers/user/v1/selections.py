from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import UnitOfWorkDep
from src.api.dependencies.repositories import (
    AssetRepositoryDep,
    CollectionRepositoryDep,
    SelectionRepositoryDep,
    VersionRepositoryDep,
)
from src.api.dependencies.services import MediaUrlsDep
from src.application import selections
from src.application.assets.dtos import AssetSummary

router = APIRouter(prefix="/selections", tags=["Подборки"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Создать подборку")
async def create_selection(
    dto: selections.CreateSelectionDTO,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> selections.SelectionResponse:
    return await selections.create_selection(
        dto,
        auth,
        selection_repository=selection_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.get("", summary="Свои и общие подборки")
async def list_selections(
    auth: CurrentUser, selection_repository: SelectionRepositoryDep
) -> list[selections.SelectionResponse]:
    return await selections.list_selections(auth, selection_repository=selection_repository)


@router.get("/{selection_id}", summary="Подборка")
async def get_selection(
    selection_id: UUID, auth: CurrentUser, selection_repository: SelectionRepositoryDep
) -> selections.SelectionResponse:
    return await selections.get_selection(selection_id, auth, selection_repository=selection_repository)


@router.get("/{selection_id}/assets", summary="Активы подборки", description="Только доступные пользователю.")
async def list_selection_assets(
    selection_id: UUID,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
) -> list[AssetSummary]:
    return await selections.list_selection_assets(
        selection_id,
        auth,
        selection_repository=selection_repository,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        media_urls=media_urls,
    )


@router.patch("/{selection_id}", summary="Изменить подборку")
async def update_selection(
    selection_id: UUID,
    dto: selections.UpdateSelectionDTO,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> selections.SelectionResponse:
    return await selections.update_selection(
        selection_id, dto, auth, selection_repository=selection_repository, uow=uow
    )


@router.delete("/{selection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить подборку")
async def delete_selection(
    selection_id: UUID, auth: CurrentUser, selection_repository: SelectionRepositoryDep, uow: UnitOfWorkDep
) -> None:
    await selections.delete_selection(selection_id, auth, selection_repository=selection_repository, uow=uow)


@router.post("/{selection_id}/assets", summary="Добавить активы")
async def add_assets(
    selection_id: UUID,
    dto: selections.SelectionItemsDTO,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> selections.SelectionResponse:
    return await selections.add_selection_assets(
        selection_id,
        dto,
        auth,
        selection_repository=selection_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.post("/{selection_id}/assets/remove", summary="Убрать активы")
async def remove_assets(
    selection_id: UUID,
    dto: selections.SelectionItemsDTO,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> selections.SelectionResponse:
    return await selections.remove_selection_assets(
        selection_id, dto, auth, selection_repository=selection_repository, uow=uow
    )


@router.put("/{selection_id}/order", summary="Изменить порядок")
async def reorder(
    selection_id: UUID,
    dto: selections.SelectionItemsDTO,
    auth: CurrentUser,
    selection_repository: SelectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> selections.SelectionResponse:
    return await selections.reorder_selection(
        selection_id, dto, auth, selection_repository=selection_repository, uow=uow
    )

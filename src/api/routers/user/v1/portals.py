from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import UnitOfWorkDep
from src.api.dependencies.repositories import (
    AssetRepositoryDep,
    CollectionRepositoryDep,
    PortalRepositoryDep,
    SelectionRepositoryDep,
)
from src.api.dependencies.services import PortalSecretsDep
from src.application.portals import usecases
from src.application.portals.dtos import CreatePortalDTO, PortalResponse, UpdatePortalDTO

router = APIRouter(prefix="/portals", tags=["Порталы"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать портал",
    description=(
        "Источники блоков должны быть доступны автору. Публичная страница: /api/public/v1/portals/{slug}."
    ),
)
async def create_portal(
    dto: CreatePortalDTO,
    auth: CurrentUser,
    portals: PortalRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    selections: SelectionRepositoryDep,
    secrets: PortalSecretsDep,
    uow: UnitOfWorkDep,
) -> PortalResponse:
    return await usecases.create_portal(
        dto,
        auth,
        portal_repository=portals,
        asset_repository=assets,
        collection_repository=collections,
        selection_repository=selections,
        secrets=secrets,
        uow=uow,
    )


@router.get("", summary="Мои порталы")
async def list_portals(auth: CurrentUser, portals: PortalRepositoryDep) -> list[PortalResponse]:
    return await usecases.list_portals(auth, portal_repository=portals)


@router.get("/{portal_id}", summary="Портал")
async def get_portal(portal_id: UUID, auth: CurrentUser, portals: PortalRepositoryDep) -> PortalResponse:
    return await usecases.get_portal(portal_id, auth, portal_repository=portals)


@router.patch("/{portal_id}", summary="Изменить, опубликовать или снять с публикации")
async def update_portal(
    portal_id: UUID,
    dto: UpdatePortalDTO,
    auth: CurrentUser,
    portals: PortalRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    selections: SelectionRepositoryDep,
    secrets: PortalSecretsDep,
    uow: UnitOfWorkDep,
) -> PortalResponse:
    return await usecases.update_portal(
        portal_id,
        dto,
        auth,
        portal_repository=portals,
        asset_repository=assets,
        collection_repository=collections,
        selection_repository=selections,
        secrets=secrets,
        uow=uow,
    )


@router.delete("/{portal_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить портал")
async def delete_portal(
    portal_id: UUID, auth: CurrentUser, portals: PortalRepositoryDep, uow: UnitOfWorkDep
) -> None:
    await usecases.delete_portal(portal_id, auth, portal_repository=portals, uow=uow)

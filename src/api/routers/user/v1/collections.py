from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import UnitOfWorkDep
from src.api.dependencies.repositories import CollectionRepositoryDep, MemberRepositoryDep, UserRepositoryDep
from src.application.collections import usecases
from src.application.collections.dtos import (
    CollectionResponse,
    CreateCollectionDTO,
    MemberDTO,
    MemberResponse,
    UpdateCollectionDTO,
)

router = APIRouter(prefix="/collections", tags=["Коллекции"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Создать коллекцию")
async def create_collection(
    dto: CreateCollectionDTO, auth: CurrentUser, collections: CollectionRepositoryDep, uow: UnitOfWorkDep
) -> CollectionResponse:
    return await usecases.create_collection(dto, auth, collection_repository=collections, uow=uow)


@router.get("", summary="Доступные коллекции")
async def list_collections(
    auth: CurrentUser, collections: CollectionRepositoryDep
) -> list[CollectionResponse]:
    return await usecases.list_collections(auth, collection_repository=collections)


@router.get("/{collection_id}", summary="Коллекция")
async def get_collection(
    collection_id: UUID, auth: CurrentUser, collections: CollectionRepositoryDep
) -> CollectionResponse:
    return await usecases.get_collection(collection_id, auth, collection_repository=collections)


@router.patch("/{collection_id}", summary="Изменить коллекцию", description="Право manage.")
async def update_collection(
    collection_id: UUID,
    dto: UpdateCollectionDTO,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> CollectionResponse:
    return await usecases.update_collection(
        collection_id, dto, auth, collection_repository=collections, uow=uow
    )


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пустую коллекцию",
    description="Только владелец. Активы нужно перенести или удалить из корзины.",
)
async def delete_collection(
    collection_id: UUID, auth: CurrentUser, collections: CollectionRepositoryDep, uow: UnitOfWorkDep
) -> None:
    await usecases.delete_collection(collection_id, auth, collection_repository=collections, uow=uow)


@router.get("/{collection_id}/members", summary="Участники")
async def list_members(
    collection_id: UUID,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    members: MemberRepositoryDep,
    users: UserRepositoryDep,
) -> list[MemberResponse]:
    return await usecases.list_members(
        collection_id,
        auth,
        collection_repository=collections,
        member_repository=members,
        user_repository=users,
    )


@router.put(
    "/{collection_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Добавить участника или сменить роль",
)
async def set_member(
    collection_id: UUID,
    dto: MemberDTO,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    members: MemberRepositoryDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.set_member(
        collection_id, dto, auth, collection_repository=collections, member_repository=members, uow=uow
    )


@router.delete(
    "/{collection_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить участника",
    description="Менеджер удаляет любого, участник может выйти сам.",
)
async def remove_member(
    collection_id: UUID,
    user_id: UUID,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    members: MemberRepositoryDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.remove_member(
        collection_id, user_id, auth, collection_repository=collections, member_repository=members, uow=uow
    )

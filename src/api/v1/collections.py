from fastapi import APIRouter, status

from src.core.collections.dtos import CollectionResponse, CreateCollectionDTO, UpdateCollectionDTO
from src.modules.auth import CurrentUser

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать коллекцию",
)
async def create_collection(
    user: CurrentUser,
    dto: CreateCollectionDTO,
) -> CollectionResponse: ...


@router.patch(
    path="/{collection_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить коллекцию",
)
async def update_collection(
    user: CurrentUser,
    dto: UpdateCollectionDTO,
) -> CollectionResponse: ...


@router.put(
    path="/{collection_id}/settings",
    status_code=status.HTTP_200_OK,
    summary="Обновить настройки коллекции",
)
async def update_collection_settings() -> CollectionResponse: ...


@router.post(
    path="/{collection_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Создать участника коллекции",
)
async def create_collection_member(): ...


@router.get(
    path="/{collection_id}/members",
    status_code=status.HTTP_200_OK,
    summary="Получить участников коллекции"
)
async def get_collection_members() -> list[...]: ...

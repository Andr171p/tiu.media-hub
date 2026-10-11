from typing import Annotated

from fastapi import APIRouter, Query, status

from src.api.dependencies import CollectionAccessDep, CurrentUser, DBSession
from src.api.presenters import PresenterDep
from src.core.common.schemas import Page
from src.modules import collections
from src.modules.collections import (
    CollectionFilters,
    CollectionResponse,
    CollectionSettings,
    CreateCollectionDTO,
    UpdateCollectionDTO,
)
from src.worker.indexing import remove_collection
from src.worker.processing import rerender_collection_previews

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", summary="Доступные коллекции")
async def list_collections(
    db: DBSession,
    presenter: PresenterDep,
    user: CurrentUser,
    filters: Annotated[CollectionFilters, Query()],
) -> Page[CollectionResponse]:
    accesses, total = await collections.list_collections(db, user, filters)
    items = await presenter.collections(db, accesses)
    return Page(items=items, total=total, limit=filters.limit, offset=filters.offset)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Создать коллекцию")
async def create_collection(
    db: DBSession,
    presenter: PresenterDep,
    user: CurrentUser,
    dto: CreateCollectionDTO,
) -> CollectionResponse:
    access = await collections.create_collection(db, user, dto)
    await db.commit()
    return await presenter.collection(db, access)


@router.get("/{collection_id}", summary="Получить коллекцию")
async def get_collection(
    db: DBSession, presenter: PresenterDep, access: CollectionAccessDep
) -> CollectionResponse:
    return await presenter.collection(db, access)


@router.patch(
    "/{collection_id}",
    summary="Обновить коллекцию",
    description="Название и описание меняют модераторы, видимость — только владелец.",
)
async def update_collection(
    db: DBSession,
    presenter: PresenterDep,
    access: CollectionAccessDep,
    dto: UpdateCollectionDTO,
) -> CollectionResponse:
    await collections.update_collection(access, dto)
    await db.commit()
    return await presenter.collection(db, access)


@router.put(
    "/{collection_id}/settings",
    summary="Настройки коллекции",
    description=(
        "Политика загрузки, схема кастомных метаданных, требования к лицензии и водяной знак. "
        "При смене водяного знака превью перерисовываются в фоне."
    ),
)
async def update_settings(
    db: DBSession,
    presenter: PresenterDep,
    user: CurrentUser,
    access: CollectionAccessDep,
    settings: CollectionSettings,
) -> CollectionResponse:
    watermark_changed = await collections.update_settings(db, access, settings, user)
    await db.commit()

    if watermark_changed:
        await rerender_collection_previews.kiq(str(access.collection.id))
    return await presenter.collection(db, access)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить коллекцию")
async def delete_collection(db: DBSession, access: CollectionAccessDep) -> None:
    await collections.delete_collection(access)
    await db.commit()
    await remove_collection.kiq(str(access.collection.id))

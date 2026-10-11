from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Query

from src.api.dependencies import DBSession
from src.api.presenters import PresenterDep
from src.core.common.schemas import Page
from src.modules import assets, collections
from src.modules.assets import AssetFilters, AssetResponse
from src.modules.collections import CollectionAccess, CollectionResponse, CollectionRole

router = APIRouter(prefix="/collections", tags=["Client: Collections"])


async def _read_access(db: DBSession, collection_id: UUID) -> CollectionAccess:
    return CollectionAccess(await collections.get_collection(db, collection_id), CollectionRole.VIEWER)


@router.get("/{collection_id}", summary="Получить коллекцию")
async def get_collection(db: DBSession, presenter: PresenterDep, collection_id: UUID) -> CollectionResponse:
    return await presenter.collection(db, await _read_access(db, collection_id))


@router.get("/{collection_id}/assets", summary="Активы коллекции")
async def list_assets(
    db: DBSession,
    presenter: PresenterDep,
    collection_id: UUID,
    filters: Annotated[AssetFilters, Query()],
) -> Page[AssetResponse]:
    items, total = await assets.list_assets(db, await _read_access(db, collection_id), filters)
    return Page(
        items=await presenter.assets(db, items, user=None),
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )

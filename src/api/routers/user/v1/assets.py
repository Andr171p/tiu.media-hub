from typing import Annotated

from fastapi import APIRouter, Query, status

from src.api.dependencies import (
    AssetContextDep,
    CdnDep,
    CollectionAccessDep,
    CurrentUser,
    DBSession,
    SearchDep,
)
from src.api.presenters import present_asset, present_assets
from src.core.common.schemas import Page
from src.modules import assets, collections
from src.modules.assets import (
    AssetFilters,
    AssetResponse,
    CreateAssetDTO,
    SetTagsDTO,
    UpdateAssetDTO,
)
from src.modules.search import SearchScope
from src.worker.indexing import index_asset
from src.worker.processing import process_version

router = APIRouter(tags=["Assets"])


@router.get("/collections/{collection_id}/assets", summary="Активы коллекции")
async def list_assets(
    db: DBSession,
    cdn: CdnDep,
    user: CurrentUser,
    access: CollectionAccessDep,
    filters: Annotated[AssetFilters, Query()],
) -> Page[AssetResponse]:
    items, total = await assets.list_assets(db, access, filters)
    return Page(
        items=await present_assets(db, cdn, items, user=user),
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.post(
    "/collections/{collection_id}/assets",
    status_code=status.HTTP_201_CREATED,
    summary="Создать актив",
    description=(
        "Создаёт актив из подтверждённой загрузки. Файл проверяется и обрабатывается в фоне: "
        "версия станет текущей, когда будут готовы метаданные и превью."
    ),
)
async def create_asset(
    db: DBSession,
    cdn: CdnDep,
    user: CurrentUser,
    access: CollectionAccessDep,
    dto: CreateAssetDTO,
) -> AssetResponse:
    asset, version = await assets.create_asset(db, access, user, dto)
    await db.commit()
    await process_version.kiq(str(version.id))

    return await present_asset(db, cdn, await assets.get_context(db, asset.id, user))


@router.get("/assets/{asset_id}", summary="Получить актив")
async def get_asset(db: DBSession, cdn: CdnDep, context: AssetContextDep) -> AssetResponse:
    return await present_asset(db, cdn, context)


@router.patch(
    "/assets/{asset_id}",
    summary="Обновить актив",
    description="Название, описание, кастомные метаданные, лицензия, архивирование.",
)
async def update_asset(
    db: DBSession,
    cdn: CdnDep,
    user: CurrentUser,
    context: AssetContextDep,
    dto: UpdateAssetDTO,
) -> AssetResponse:
    await assets.update_asset(db, context, dto)
    await db.commit()
    await index_asset.kiq(str(context.asset.id))

    return await present_asset(db, cdn, await assets.get_context(db, context.asset.id, user))


@router.put("/assets/{asset_id}/tags", summary="Заменить теги актива")
async def set_tags(
    db: DBSession,
    cdn: CdnDep,
    user: CurrentUser,
    context: AssetContextDep,
    dto: SetTagsDTO,
) -> AssetResponse:
    await assets.set_tags(db, context, dto.tags)
    await db.commit()
    await index_asset.kiq(str(context.asset.id))

    return await present_asset(db, cdn, await assets.get_context(db, context.asset.id, user))


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить актив")
async def delete_asset(db: DBSession, context: AssetContextDep) -> None:
    await assets.delete_asset(db, context)
    await db.commit()
    await index_asset.kiq(str(context.asset.id))


@router.get("/assets/{asset_id}/similar", summary="Похожие изображения")
async def similar_assets(
    db: DBSession,
    cdn: CdnDep,
    search: SearchDep,
    user: CurrentUser,
    context: AssetContextDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> list[AssetResponse]:
    allowed = await collections.accessible_collection_ids(db, user)
    scope = SearchScope(collection_ids=frozenset(allowed) if allowed is not None else None)
    items = await search.similar(db, context.asset.id, scope, limit=limit)
    return await present_assets(db, cdn, items, user=user)

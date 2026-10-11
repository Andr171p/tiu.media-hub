from fastapi import APIRouter

from src.api.dependencies import CdnDep, CurrentUser, DBSession, SearchDep
from src.api.presenters import present_assets
from src.modules import collections
from src.modules.search import SearchDTO, SearchResponse, build_scope

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "",
    summary="Поиск активов",
    description=(
        "Text-to-image: запрос сравнивается со смыслом изображений (CLIP) и с текстом "
        "(название, описание, теги, метаданные, текст документов). Только по доступным коллекциям."
    ),
)
async def search_assets(
    db: DBSession,
    cdn: CdnDep,
    search: SearchDep,
    user: CurrentUser,
    dto: SearchDTO,
) -> SearchResponse:
    scope = build_scope(dto, await collections.accessible_collection_ids(db, user))
    items, has_more = await search.search(db, dto, scope)

    return SearchResponse(
        items=await present_assets(db, cdn, items, user=user),
        limit=dto.limit,
        offset=dto.offset,
        has_more=has_more,
    )

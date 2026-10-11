from typing import Annotated

from fastapi import APIRouter, Query

from src.api.dependencies import CurrentUser, DBSession
from src.modules import tags
from src.modules.tags import TagResponse

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("", summary="Подсказки тегов")
async def search_tags(
    db: DBSession,
    _: CurrentUser,
    query: Annotated[str, Query(max_length=64)] = "",
) -> list[TagResponse]:
    return [TagResponse.model_validate(tag) for tag in await tags.search_tags(db, query)]

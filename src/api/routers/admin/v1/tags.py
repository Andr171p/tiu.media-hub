from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.dependencies import DBSession
from src.modules import tags
from src.modules.tags import CreateTagDTO, TagResponse, UpdateTagDTO
from src.worker.indexing import sync_tag_vocabulary

router = APIRouter(
    prefix="/tags",
    tags=["Admin: Tags"],
    responses={status.HTTP_403_FORBIDDEN: {"description": "Нужна роль admin"}},
)


@router.get("", summary="Словарь тегов")
async def list_tags(
    db: DBSession,
    auto_assign: Annotated[
        bool | None, Query(alias="autoAssign", description="Только теги автотегирования")
    ] = None,
) -> list[TagResponse]:
    return await tags.list_tags(db, auto_assign=auto_assign)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить тег",
    description="Теги с autoAssign назначаются автоматически по содержимому изображения новых версий.",
)
async def create_tag(db: DBSession, dto: CreateTagDTO) -> TagResponse:
    tag = await tags.create_tag(db, dto)
    await db.commit()
    await sync_tag_vocabulary.kiq()
    return TagResponse.model_validate(tag)


@router.patch("/{tag_id}", summary="Изменить тег")
async def update_tag(db: DBSession, tag_id: UUID, dto: UpdateTagDTO) -> TagResponse:
    tag = await tags.update_tag(db, tag_id, dto)
    await db.commit()
    await sync_tag_vocabulary.kiq()
    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить тег")
async def delete_tag(db: DBSession, tag_id: UUID) -> None:
    await tags.delete_tag(db, tag_id)
    await db.commit()
    await sync_tag_vocabulary.kiq()

from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import UnitOfWorkDep
from src.api.dependencies.repositories import (
    AssetRepositoryDep,
    CollectionRepositoryDep,
    CommentRepositoryDep,
)
from src.application import comments

router = APIRouter(prefix="/comments", tags=["Комментарии"])


@router.post("/{comment_id}/replies", status_code=status.HTTP_201_CREATED, summary="Ответить в обсуждении")
async def reply(
    comment_id: UUID,
    dto: comments.ReplyDTO,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> comments.CommentResponse:
    return await comments.reply_to_comment(
        comment_id,
        dto,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.patch("/{comment_id}", summary="Изменить текст (автор)")
async def edit(
    comment_id: UUID,
    dto: comments.ReplyDTO,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> comments.CommentResponse:
    return await comments.edit_comment(
        comment_id,
        dto,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.delete(
    "/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить (автор или менеджер)"
)
async def delete(
    comment_id: UUID,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> None:
    await comments.delete_comment(
        comment_id,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.post("/{comment_id}/resolve", summary="Отметить обсуждение решённым")
async def resolve(
    comment_id: UUID,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> comments.CommentResponse:
    return await comments.set_comment_resolved(
        comment_id,
        True,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )


@router.post("/{comment_id}/reopen", summary="Переоткрыть обсуждение")
async def reopen(
    comment_id: UUID,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    uow: UnitOfWorkDep,
) -> comments.CommentResponse:
    return await comments.set_comment_resolved(
        comment_id,
        False,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        uow=uow,
    )

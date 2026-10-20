"""Комментарии к активам: обсуждения с отметкой области изображения или момента видео."""

from typing import Annotated, Literal

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.repositories import Repository
from ddf.application.uow import UnitOfWork
from pydantic import Field

from src.application.assets.access import get_asset_access
from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser, PermissionDeniedError
from src.application.collections.repositories import CollectionRepository
from src.application.dtos import CamelModel
from src.domain.collections import Permission
from src.domain.comments import Anchor, Comment, Region, TimeRange

type Text = Annotated[str, Field(min_length=1, max_length=5000)]


class CommentRepository(Repository[Comment]):
    async def list_by_asset(self, asset_id: UUID) -> Sequence[Comment]:
        """Комментарии актива в хронологическом порядке."""
        raise NotImplementedError


class RegionDTO(CamelModel):
    type: Literal["region"] = "region"
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class TimeRangeDTO(CamelModel):
    type: Literal["time"] = "time"
    start: float = Field(ge=0, description="Секунды")
    end: float | None = Field(default=None, ge=0)


type AnchorDTO = Annotated[RegionDTO | TimeRangeDTO, Field(discriminator="type")]


class CreateCommentDTO(CamelModel):
    text: Text
    version_id: UUID | None = Field(default=None, description="По умолчанию — текущая версия")
    anchor: AnchorDTO | None = Field(default=None, description="Область изображения или момент видео")


class ReplyDTO(CamelModel):
    text: Text


class CommentResponse(CamelModel):
    id: UUID
    asset_id: UUID
    version_id: UUID
    author_id: UUID
    text: str
    anchor: AnchorDTO | None
    parent_id: UUID | None
    resolved_at: datetime | None
    resolved_by: UUID | None
    created_at: datetime
    updated_at: datetime
    replies: list[CommentResponse] = Field(default_factory=list)


def _to_anchor(dto: AnchorDTO | None) -> Anchor | None:
    match dto:
        case RegionDTO():
            return Region(x=dto.x, y=dto.y, width=dto.width, height=dto.height)
        case TimeRangeDTO():
            return TimeRange(start=dto.start, end=dto.end)
    return None


def _present(comment: Comment, replies: Sequence[Comment] = ()) -> CommentResponse:
    response = CommentResponse.model_validate(comment)
    response.replies = [CommentResponse.model_validate(reply) for reply in replies]
    return response


async def _read_comment(
    comment_id: UUID,
    auth: AuthUser,
    permission: Permission,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
) -> tuple[Comment, frozenset[Permission]]:
    if (comment := await comment_repository.read(comment_id)) is None:
        raise NotFoundError(f"Comment with ID {comment_id} not found.")

    access = await get_asset_access(
        comment.asset_id,
        auth,
        permission,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    return comment, access.permissions


async def list_comments(
    asset_id: UUID,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
) -> list[CommentResponse]:
    """Обсуждения актива (по всем версиям) с ответами."""

    await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    comments = await comment_repository.list_by_asset(asset_id)

    replies: dict[UUID, list[Comment]] = {}
    for comment in comments:
        if comment.parent_id is not None:
            replies.setdefault(comment.parent_id, []).append(comment)

    return [_present(comment, replies.get(comment.id, ())) for comment in comments if comment.is_thread]


async def create_comment(
    asset_id: UUID,
    dto: CreateCommentDTO,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    uow: UnitOfWork,
) -> CommentResponse:
    access = await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    version_id = dto.version_id or access.asset.current_version_id

    version = await version_repository.read(version_id)
    if version is None or version.asset_id != asset_id:
        raise NotFoundError(f"Version with ID {version_id} not found.")

    comment = Comment(
        asset_id=asset_id,
        version_id=version_id,
        author_id=auth.user_id,
        text=dto.text,
        anchor=_to_anchor(dto.anchor),
    )
    await comment_repository.create(comment)
    await uow.commit()

    return _present(comment)


async def reply_to_comment(
    comment_id: UUID,
    dto: ReplyDTO,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> CommentResponse:
    thread, _ = await _read_comment(
        comment_id,
        auth,
        Permission.READ,
        comment_repository=comment_repository,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    reply = thread.reply(author_id=auth.user_id, text=dto.text)

    await comment_repository.create(reply)
    await uow.commit()

    return _present(reply)


async def edit_comment(
    comment_id: UUID,
    dto: ReplyDTO,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> CommentResponse:
    comment, _ = await _read_comment(
        comment_id,
        auth,
        Permission.READ,
        comment_repository=comment_repository,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if comment.author_id != auth.user_id:
        raise PermissionDeniedError("Only the author can edit a comment.")

    comment.text = dto.text
    comment.updated_at = datetime.now(UTC)

    await comment_repository.update(comment)
    await uow.commit()

    return _present(comment)


async def delete_comment(
    comment_id: UUID,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> None:
    """Удаляет автор или менеджер коллекции; вместе с обсуждением удаляются ответы."""

    comment, permissions = await _read_comment(
        comment_id,
        auth,
        Permission.READ,
        comment_repository=comment_repository,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if comment.author_id != auth.user_id and Permission.MANAGE not in permissions:
        raise PermissionDeniedError("Only the author or a collection manager can delete a comment.")

    await comment_repository.delete(comment.id)
    await uow.commit()


async def set_comment_resolved(
    comment_id: UUID,
    resolved: bool,
    auth: AuthUser,
    *,
    comment_repository: CommentRepository,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> CommentResponse:
    comment, _ = await _read_comment(
        comment_id,
        auth,
        Permission.READ,
        comment_repository=comment_repository,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if resolved:
        comment.resolve(by=auth.user_id)
    else:
        comment.reopen()

    await comment_repository.update(comment)
    await uow.commit()

    return _present(comment)

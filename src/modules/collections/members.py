from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth import AuthUser
from src.core.common.exceptions import ConflictError, InvalidDataError, NotFoundError
from src.modules.users import User

from .access import Action, CollectionAccess
from .models import CollectionMember, MemberRole
from .schemas import AddMemberDTO, UpdateMemberDTO


def _required_action(role: MemberRole) -> Action:
    """Участниками управляют модераторы, модераторами — только владелец."""

    return Action.MANAGE if role is MemberRole.MODERATOR else Action.MODERATE


async def list_members(session: AsyncSession, access: CollectionAccess) -> Sequence[CollectionMember]:
    access.require(Action.VIEW)
    stmt = (
        select(CollectionMember)
        .options(selectinload(CollectionMember.user))
        .where(CollectionMember.collection_id == access.collection.id)
        .order_by(CollectionMember.role.desc(), CollectionMember.created_at)
    )
    return (await session.scalars(stmt)).all()


async def _get_member(session: AsyncSession, access: CollectionAccess, user_id: UUID) -> CollectionMember:
    member = await session.scalar(
        select(CollectionMember)
        .options(selectinload(CollectionMember.user))
        .where(
            CollectionMember.collection_id == access.collection.id,
            CollectionMember.user_id == user_id,
        ),
    )
    if member is None:
        raise NotFoundError("Member not found.")
    return member


async def add_member(session: AsyncSession, access: CollectionAccess, dto: AddMemberDTO) -> CollectionMember:
    access.require(_required_action(dto.role))

    if dto.user_id == access.collection.owner_id:
        raise InvalidDataError("Owner already has full access to the collection.")

    if (user := await session.get(User, dto.user_id)) is None:
        raise NotFoundError("User not found. They need to sign in at least once.")

    exists = await session.scalar(
        select(CollectionMember.id).where(
            CollectionMember.collection_id == access.collection.id,
            CollectionMember.user_id == dto.user_id,
        ),
    )
    if exists is not None:
        raise ConflictError("User is already a member of the collection.")

    member = CollectionMember(collection_id=access.collection.id, user_id=dto.user_id, role=dto.role)
    session.add(member)
    await session.flush()

    member.user = user
    return member


async def update_member(
    session: AsyncSession,
    access: CollectionAccess,
    user_id: UUID,
    dto: UpdateMemberDTO,
) -> CollectionMember:
    access.require(Action.MANAGE)
    member = await _get_member(session, access, user_id)
    member.role = dto.role
    return member


async def remove_member(
    session: AsyncSession, access: CollectionAccess, user_id: UUID, user: AuthUser
) -> None:
    member = await _get_member(session, access, user_id)

    # Покинуть коллекцию может любой участник
    if user_id != user.user.id:
        access.require(_required_action(member.role))

    await session.delete(member)


__all__ = ["add_member", "list_members", "remove_member", "update_member"]

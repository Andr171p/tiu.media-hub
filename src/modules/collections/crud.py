from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.collections.dtos import CreateCollectionDTO, UpdateCollectionDTO
from src.core.collections.models import Collection, CollectionMember
from src.core.common.crud import Crud

crud = Crud[
    Collection,
    CreateCollectionDTO,
    UpdateCollectionDTO,
    None,
    None,
    None,
    None,
](Collection)


async def get_collection_members(
    session: AsyncSession,
    collection_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[CollectionMember]:
    """Получение участников коллекции."""

    stmt = (
        select(CollectionMember)
        .where(CollectionMember.collection_id == collection_id)
        .limit(limit)
        .offset(offset)
    )
    results = await session.execute(stmt)
    return results.scalars().all()


async def get_collection_member(
    session: AsyncSession,
    collection_id: UUID,
    user_id: UUID,
) -> CollectionMember | None:
    """Получение участника коллекции по его составному идентификатору."""

    stmt = select(CollectionMember).where(
        (CollectionMember.collection_id == collection_id)
        & (CollectionMember.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

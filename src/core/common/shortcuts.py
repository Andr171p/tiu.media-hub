from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.base import Base


async def get_or_raise_404[ModelT: Base](
    session: AsyncSession,
    model: type[ModelT],
    uid: UUID,
    *,
    for_update: bool = False,
) -> ModelT:
    stmt = select(model).where((model.id == uid) & (model.deleted_at.is_(None)))

    if for_update:
        stmt = stmt.with_for_update()

    if (obj := await session.scalar(stmt)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__.lower().capitalize()} with ID {uid} not found.",
        )

    return obj

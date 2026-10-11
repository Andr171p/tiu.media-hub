from typing import Annotated

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Сессия на запрос: незакоммиченные изменения откатываются при закрытии."""

    async with request.app.state.session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

__all__ = ["DBSession"]

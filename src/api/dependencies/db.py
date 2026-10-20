from typing import Annotated

from collections.abc import AsyncIterator

from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork
from ddf.infra.outbox.sqlalchemy import SqlAlchemyOutboxStore
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.outbox import OUTBOX_CHANNEL


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Сессия на запрос: незафиксированные изменения откатываются при закрытии."""

    async with request.app.state.session_factory() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


def get_uow(session: DBSession) -> UnitOfWork:
    return session


def get_outbox(session: DBSession) -> OutboxStore:
    return SqlAlchemyOutboxStore(session, notify_channel=OUTBOX_CHANNEL)


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_uow)]
OutboxDep = Annotated[OutboxStore, Depends(get_outbox)]

__all__ = ["DBSession", "OutboxDep", "UnitOfWorkDep"]

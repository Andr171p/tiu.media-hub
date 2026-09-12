from typing import Annotated

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database.config import PostgresConfig

config = PostgresConfig()

engine = create_async_engine(url=config.uri, pool_pre_ping=True)
sessionmaker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

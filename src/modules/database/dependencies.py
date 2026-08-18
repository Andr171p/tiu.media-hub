from typing import Annotated

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.common.models import Base
from src.core.database.config import PostgresConfig

config = PostgresConfig()

engine = create_async_engine(url=config.uri, echo=True)
sessionmaker = async_sessionmaker(
    engine, class_=AsyncSession, autoflush=False, expire_on_commit=False,
)


async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db() -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

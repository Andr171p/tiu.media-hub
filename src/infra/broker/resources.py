"""Composition root воркеров: долгоживущие клиенты создаются при старте процесса."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from ddf.infra.database.sqlalchemy import PostgresConfig
from ddf.infra.outbox.sqlalchemy import SqlAlchemyOutboxStore
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.infra.database.session import create_engine, create_session_factory
from src.infra.media.processor import FfmpegMediaProcessor, MediaConfig
from src.infra.outbox import OUTBOX_CHANNEL
from src.infra.storage.config import StorageConfig
from src.infra.storage.s3 import S3FileStorage


@dataclass(slots=True)
class WorkerResources:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    originals: S3FileStorage
    renditions: S3FileStorage
    processor: FfmpegMediaProcessor

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    @staticmethod
    def outbox(session: AsyncSession) -> SqlAlchemyOutboxStore:
        return SqlAlchemyOutboxStore(session, notify_channel=OUTBOX_CHANNEL)

    async def close(self) -> None:
        await self.engine.dispose()


def create_worker_resources() -> WorkerResources:
    engine = create_engine(PostgresConfig())
    storage_config = StorageConfig()

    return WorkerResources(
        engine=engine,
        session_factory=create_session_factory(engine),
        originals=S3FileStorage(storage_config, storage_config.originals_bucket),
        renditions=S3FileStorage(storage_config, storage_config.renditions_bucket),
        processor=FfmpegMediaProcessor(MediaConfig()),
    )


__all__ = ["WorkerResources", "create_worker_resources"]

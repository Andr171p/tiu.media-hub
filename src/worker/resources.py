"""Composition root воркеров: зависимости создаются при старте процесса, а не через FastAPI ``Depends``."""

import logging
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from taskiq import TaskiqDepends, TaskiqState

from src.core.database import PostgresConfig, create_engine, create_session_factory
from src.core.infinity import InfinityClient, InfinityConfig
from src.core.qdrant import QdrantConfig, create_qdrant_client
from src.core.s3 import S3Client, S3Config
from src.modules.processing import ProcessingConfig, VersionProcessor
from src.modules.search import AssetIndexer, AssetSearchIndex, SearchConfig


@dataclass(slots=True)
class Resources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    s3: S3Client
    qdrant: AsyncQdrantClient
    embedder: InfinityClient
    processor: VersionProcessor
    indexer: AssetIndexer


async def create_resources() -> Resources:
    logging.basicConfig(level=logging.INFO)

    engine = create_engine(PostgresConfig())
    sessions = create_session_factory(engine)

    s3 = S3Client(S3Config())  # type: ignore[call-arg]
    await s3.connect()

    infinity_config = InfinityConfig()
    embedder = InfinityClient(infinity_config)

    qdrant = create_qdrant_client(QdrantConfig())
    index = AssetSearchIndex(qdrant, QdrantConfig(), dimensions=infinity_config.dimensions)
    await index.ensure_collections()

    return Resources(
        engine=engine,
        sessions=sessions,
        s3=s3,
        qdrant=qdrant,
        embedder=embedder,
        processor=VersionProcessor(sessions, s3, ProcessingConfig()),
        indexer=AssetIndexer(sessions, s3, embedder, index, SearchConfig()),
    )


async def close_resources(resources: Resources) -> None:
    await resources.embedder.close()
    await resources.qdrant.close()
    await resources.s3.close()
    await resources.engine.dispose()


def get_resources(state: TaskiqState = TaskiqDepends()) -> Resources:  # noqa: B008
    return state.resources


__all__ = ["Resources", "close_resources", "create_resources", "get_resources"]

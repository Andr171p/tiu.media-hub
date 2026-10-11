from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.cdn import CdnClient, CdnConfig
from src.core.database import PostgresConfig, create_engine, create_session_factory
from src.core.infinity import InfinityClient, InfinityConfig
from src.core.keycloak import KeycloakClient, KeycloakConfig
from src.core.qdrant import QdrantConfig, create_qdrant_client
from src.core.s3 import S3Client, S3Config
from src.modules.media import UploadConfig
from src.modules.search import AssetSearch, AssetSearchIndex, SearchConfig
from src.worker.brokers import indexing_broker, processing_broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Composition root API: создаёт долгоживущие клиенты и закрывает их при остановке."""

    engine = create_engine(PostgresConfig())
    keycloak = KeycloakClient(KeycloakConfig())  # type: ignore[call-arg]

    s3 = S3Client(S3Config())  # type: ignore[call-arg]
    await s3.connect()

    infinity_config = InfinityConfig()
    embedder = InfinityClient(infinity_config)

    qdrant_config = QdrantConfig()
    qdrant = create_qdrant_client(qdrant_config)
    index = AssetSearchIndex(qdrant, qdrant_config, dimensions=infinity_config.dimensions)
    await index.ensure_collections()

    await processing_broker.startup()
    await indexing_broker.startup()

    app.state.session_factory = create_session_factory(engine)
    app.state.keycloak_client = keycloak
    app.state.s3 = s3
    app.state.cdn = CdnClient(CdnConfig())  # type: ignore[call-arg]
    app.state.search = AssetSearch(index, embedder, SearchConfig())
    app.state.upload_config = UploadConfig()

    try:
        yield
    finally:
        await indexing_broker.shutdown()
        await processing_broker.shutdown()
        await qdrant.close()
        await embedder.close()
        await s3.close()
        await keycloak.close()
        await engine.dispose()


__all__ = ["lifespan"]

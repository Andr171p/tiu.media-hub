from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ddf.infra.cache import InMemoryCache
from ddf.infra.database.sqlalchemy import PostgresConfig
from ddf.infra.integrations.keycloak import KeycloakConfig
from fastapi import FastAPI

from src.infra.ai.infinity import InfinityClipEmbedder, InfinityConfig
from src.infra.auth import ClientsConfig, KeycloakAuthenticator
from src.infra.broker.ai_tasks import ai_broker
from src.infra.broker.media_tasks import TaskiqEditQueue, media_broker
from src.infra.database.session import create_engine, create_session_factory
from src.infra.media.faces import FacesConfig, OpenCvFaceAnalyzer
from src.infra.qdrant import QdrantConfig, QdrantFaceIndex, QdrantVisualIndex, create_qdrant_client
from src.infra.security import HmacPortalSecrets, PortalSecretsConfig
from src.infra.storage.cdn import SignedCdnUrls
from src.infra.storage.config import CdnConfig, StorageConfig
from src.infra.storage.s3 import S3FileStorage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Composition root API: долгоживущие клиенты создаются при старте и закрываются при остановке."""

    engine = create_engine(PostgresConfig())
    storage_config = StorageConfig()
    authenticator = KeycloakAuthenticator(KeycloakConfig(), ClientsConfig())  # type: ignore[call-arg]

    qdrant_config = QdrantConfig()
    qdrant = create_qdrant_client(qdrant_config)
    visual_index = QdrantVisualIndex(qdrant, qdrant_config)
    face_index = QdrantFaceIndex(qdrant, qdrant_config)
    await visual_index.ensure_collection()
    await face_index.ensure_collection()

    embedder = InfinityClipEmbedder(InfinityConfig())
    await media_broker.startup()
    await ai_broker.startup()

    app.state.session_factory = create_session_factory(engine)
    app.state.authenticator = authenticator
    app.state.profile_cache = InMemoryCache[bool]()
    app.state.originals = S3FileStorage(storage_config, storage_config.originals_bucket)
    app.state.renditions = S3FileStorage(storage_config, storage_config.renditions_bucket)
    app.state.media_urls = SignedCdnUrls(CdnConfig())
    app.state.embedder = embedder
    app.state.visual_index = visual_index
    app.state.face_index = face_index
    app.state.face_analyzer = OpenCvFaceAnalyzer(FacesConfig())
    app.state.portal_secrets = HmacPortalSecrets(PortalSecretsConfig())
    app.state.edit_queue = TaskiqEditQueue()

    try:
        yield
    finally:
        await ai_broker.shutdown()
        await media_broker.shutdown()
        await embedder.close()
        await qdrant.close()
        await authenticator.close()
        await engine.dispose()


__all__ = ["lifespan"]

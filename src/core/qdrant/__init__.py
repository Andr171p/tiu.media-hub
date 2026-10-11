from qdrant_client import AsyncQdrantClient

from .config import QdrantConfig


def create_qdrant_client(config: QdrantConfig) -> AsyncQdrantClient:
    # cloud_inference: BM25-документы векторизует сервер Qdrant, а не fastembed в процессе приложения
    return AsyncQdrantClient(
        url=str(config.url),
        api_key=config.api_key.get_secret_value() if config.api_key else None,
        timeout=config.timeout,
        cloud_inference=True,
    )


__all__ = ["QdrantConfig", "create_qdrant_client"]

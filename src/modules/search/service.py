import logging
from collections.abc import Iterable, Set
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infinity import EmbeddingUnavailableError, InfinityClient
from src.modules.assets import Asset, select_assets
from src.modules.tags import normalize_tag

from .config import SearchConfig
from .index import AssetSearchIndex, Hit, SearchScope
from .schemas import SearchDTO

logger = logging.getLogger(__name__)


def build_scope(dto: SearchDTO, allowed: Set[UUID] | None) -> SearchScope:
    """Пересечение запрошенных коллекций с доступными. ``allowed=None`` — доступны все."""

    requested = set(dto.collection_ids) if dto.collection_ids is not None else None

    if allowed is None:
        collection_ids = requested
    elif requested is None:
        collection_ids = set(allowed)
    else:
        collection_ids = requested & allowed

    return SearchScope(
        collection_ids=frozenset(collection_ids) if collection_ids is not None else None,
        kinds=frozenset(kind.value for kind in dto.kinds),
        tags=frozenset(tag for raw in dto.tags if (tag := normalize_tag(raw))),
    )


async def _load_in_order(session: AsyncSession, hits: Iterable[Hit]) -> list[Asset]:
    ids = [hit.asset_id for hit in hits]
    if not ids:
        return []

    assets = {asset.id: asset for asset in await session.scalars(select_assets().where(Asset.id.in_(ids)))}
    # Индекс мог отстать от базы: удалённые после индексации активы пропускаем
    return [assets[asset_id] for asset_id in ids if asset_id in assets]


class AssetSearch:
    def __init__(self, index: AssetSearchIndex, embedder: InfinityClient, config: SearchConfig) -> None:
        self._index = index
        self._embedder = embedder
        self._config = config

    async def search(
        self, session: AsyncSession, dto: SearchDTO, scope: SearchScope
    ) -> tuple[list[Asset], bool]:
        try:
            query_vector = await self._embedder.embed_text(dto.query)
        except EmbeddingUnavailableError:
            # Без сервера эмбеддингов остаётся поиск по словам: хуже, но работает
            logger.warning("Embedding server is unavailable, falling back to text search", exc_info=True)
            query_vector = None

        hits = await self._index.search(
            query=dto.query,
            query_vector=query_vector,
            scope=scope,
            image_score_threshold=self._config.image_score_threshold,
            prefetch_limit=self._config.prefetch_limit,
            limit=dto.limit + 1,
            offset=dto.offset,
        )
        has_more = len(hits) > dto.limit
        return await _load_in_order(session, hits[: dto.limit]), has_more

    async def similar(
        self, session: AsyncSession, asset_id: UUID, scope: SearchScope, *, limit: int
    ) -> list[Asset]:
        return await _load_in_order(session, await self._index.similar(asset_id, scope=scope, limit=limit))


__all__ = ["AssetSearch", "build_scope"]

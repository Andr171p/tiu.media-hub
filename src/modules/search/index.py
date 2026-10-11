from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.infinity import Vector
from src.core.qdrant import QdrantConfig

IMAGE_VECTOR = "image"
TEXT_VECTOR = "text"
TAG_VECTOR = "prompt"
BM25_MODEL = "qdrant/bm25"

_UPSERT_BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class AssetPoint:
    asset_id: UUID
    collection_id: UUID
    kind: str
    tags: Sequence[str]
    text: str
    image_vector: Vector | None


@dataclass(frozen=True, slots=True)
class SearchScope:
    """Ограничения поиска. ``collection_ids=None`` — все коллекции (администратор, сервис)."""

    collection_ids: frozenset[UUID] | None
    kinds: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()

    @property
    def is_empty(self) -> bool:
        return self.collection_ids is not None and not self.collection_ids


@dataclass(frozen=True, slots=True)
class Hit:
    asset_id: UUID
    score: float


def _match_any(key: str, values: Sequence[str]) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchAny(any=list(values)))


class AssetSearchIndex:
    """
    Индекс активов в Qdrant: одна точка на актив (по текущей версии).

    * ``image`` — эмбеддинг миниатюры (SigLIP): поиск по смыслу изображения текстом и похожих картинок;
    * ``text`` — BM25 по названию, описанию, тегам, метаданным и тексту документа (векторизует Qdrant).

    Права проверяются фильтром по коллекциям: видимость коллекций решает PostgreSQL в момент запроса,
    поэтому смена доступа не требует переиндексации.
    """

    def __init__(self, client: AsyncQdrantClient, config: QdrantConfig, *, dimensions: int) -> None:
        self._client = client
        self._config = config
        self._dimensions = dimensions
        self._assets = config.collection_name("assets")
        self._tags = config.collection_name("tags")

    def _bm25(self, text: str) -> models.Document:
        return models.Document(text=text, model=BM25_MODEL, options={"language": self._config.bm25_language})

    async def _create_collection(self, name: str, **params: object) -> bool:
        if await self._client.collection_exists(name):
            return False
        try:
            await self._client.create_collection(name, **params)  # type: ignore[arg-type]
        except UnexpectedResponse as exc:
            # Коллекцию параллельно создал другой процесс (API или воркер)
            if exc.status_code != HTTPStatus.CONFLICT:
                raise
        return True

    async def ensure_collections(self) -> None:
        dense = models.VectorParams(size=self._dimensions, distance=models.Distance.COSINE)

        if await self._create_collection(
            self._assets,
            vectors_config={IMAGE_VECTOR: dense},
            sparse_vectors_config={TEXT_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        ):
            await self._client.create_payload_index(
                self._assets,
                "collection_id",
                models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD, is_tenant=True),
            )
            for field in ("kind", "tags"):
                await self._client.create_payload_index(self._assets, field, models.PayloadSchemaType.KEYWORD)

        await self._create_collection(self._tags, vectors_config={TAG_VECTOR: dense})

    # =============================================================================================
    # Запись
    # =============================================================================================

    async def upsert(self, point: AssetPoint) -> None:
        vector: dict[str, list[float] | models.Document] = {TEXT_VECTOR: self._bm25(point.text)}
        if point.image_vector is not None:
            vector[IMAGE_VECTOR] = point.image_vector

        await self._client.upsert(
            self._assets,
            points=[
                models.PointStruct(
                    id=str(point.asset_id),
                    vector=vector,
                    payload={
                        "asset_id": str(point.asset_id),
                        "collection_id": str(point.collection_id),
                        "kind": point.kind,
                        "tags": list(point.tags),
                    },
                ),
            ],
            wait=True,
        )

    async def get_image_vector(self, asset_id: UUID) -> Vector | None:
        points = await self._client.retrieve(
            self._assets,
            ids=[str(asset_id)],
            with_payload=False,
            with_vectors=[IMAGE_VECTOR],
        )
        if not points or not isinstance(points[0].vector, dict):
            return None
        vector = points[0].vector.get(IMAGE_VECTOR)
        return list(vector) if isinstance(vector, list) else None  # type: ignore[arg-type]

    async def delete(self, asset_id: UUID) -> None:
        await self._client.delete(
            self._assets, points_selector=models.PointIdsList(points=[str(asset_id)]), wait=True
        )

    async def delete_collection_assets(self, collection_id: UUID) -> None:
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="collection_id", match=models.MatchValue(value=str(collection_id))
                    )
                ],
            ),
        )
        await self._client.delete(self._assets, points_selector=selector, wait=True)

    # =============================================================================================
    # Поиск
    # =============================================================================================

    @staticmethod
    def _filter(scope: SearchScope, *, exclude: UUID | None = None) -> models.Filter:
        must: list[models.Condition] = []
        if scope.collection_ids is not None:
            must.append(_match_any("collection_id", [str(item) for item in scope.collection_ids]))
        if scope.kinds:
            must.append(_match_any("kind", sorted(scope.kinds)))
        # Каждый тег обязателен: пересечение, а не объединение
        must.extend(_match_any("tags", [tag]) for tag in sorted(scope.tags))

        must_not = [models.HasIdCondition(has_id=[str(exclude)])] if exclude else None
        return models.Filter(must=must, must_not=must_not)

    @staticmethod
    def _hits(points: Sequence[models.ScoredPoint]) -> list[Hit]:
        return [Hit(asset_id=UUID(str(point.id)), score=point.score) for point in points]

    async def search(
        self,
        *,
        query: str,
        query_vector: Vector | None,
        scope: SearchScope,
        image_score_threshold: float,
        prefetch_limit: int,
        limit: int,
        offset: int,
    ) -> list[Hit]:
        """Гибридный поиск: смысл изображения (SigLIP) + совпадение слов (BM25), слияние RRF."""

        if scope.is_empty:
            return []

        scope_filter = self._filter(scope)
        prefetch = [
            models.Prefetch(
                query=self._bm25(query),
                using=TEXT_VECTOR,
                filter=scope_filter,
                limit=prefetch_limit,
            ),
        ]
        if query_vector is not None:
            prefetch.append(
                models.Prefetch(
                    query=query_vector,
                    using=IMAGE_VECTOR,
                    filter=scope_filter,
                    score_threshold=image_score_threshold,
                    limit=prefetch_limit,
                ),
            )

        response = await self._client.query_points(
            self._assets,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            offset=offset,
            with_payload=False,
        )
        return self._hits(response.points)

    async def similar(self, asset_id: UUID, *, scope: SearchScope, limit: int) -> list[Hit]:
        """Визуально похожие активы: ближайшие соседи эмбеддинга изображения."""

        if scope.is_empty:
            return []

        try:
            response = await self._client.query_points(
                self._assets,
                query=str(asset_id),
                using=IMAGE_VECTOR,
                query_filter=self._filter(scope, exclude=asset_id),
                limit=limit,
                with_payload=False,
            )
        except UnexpectedResponse as exc:
            # У актива нет изображения или он ещё не проиндексирован
            if exc.status_code in {HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST}:
                return []
            raise
        return self._hits(response.points)

    # =============================================================================================
    # Словарь автотегирования
    # =============================================================================================

    async def replace_tags(self, tags: Sequence[tuple[UUID, Vector]]) -> None:
        keep = {str(tag_id) for tag_id, _ in tags}

        for start in range(0, len(tags), _UPSERT_BATCH_SIZE):
            await self._client.upsert(
                self._tags,
                points=[
                    models.PointStruct(id=str(tag_id), vector={TAG_VECTOR: vector})
                    for tag_id, vector in tags[start : start + _UPSERT_BATCH_SIZE]
                ],
                wait=True,
            )

        stale: list[models.ExtendedPointId] = []
        offset = None
        while True:
            points, offset = await self._client.scroll(
                self._tags, limit=256, offset=offset, with_payload=False
            )
            stale.extend(point.id for point in points if str(point.id) not in keep)
            if offset is None:
                break

        if stale:
            await self._client.delete(
                self._tags, points_selector=models.PointIdsList(points=stale), wait=True
            )

    async def score_tags(self, image_vector: Vector, *, limit: int) -> list[tuple[UUID, float]]:
        response = await self._client.query_points(
            self._tags,
            query=image_vector,
            using=TAG_VECTOR,
            limit=limit,
            with_payload=False,
        )
        return [(UUID(str(point.id)), point.score) for point in response.points]


__all__ = ["AssetPoint", "AssetSearchIndex", "Hit", "SearchScope"]

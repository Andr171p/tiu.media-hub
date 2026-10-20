"""
Векторные индексы Qdrant. Точки хранятся для всех версий; в поиск попадают только точки
текущей версии вне корзины (флаги ``current``/``trashed`` в payload). Права — фильтр по коллекциям.
"""

from typing import Any

import uuid
from collections.abc import Sequence
from http import HTTPStatus
from uuid import UUID

from pydantic import Field, HttpUrl, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.application.people.ports import FaceHit, FaceIndex, FacePoint
from src.application.search.ports import (
    AssetIndexState,
    SearchScope,
    VisualHit,
    VisualIndex,
    VisualPoint,
)


class QdrantConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    url: HttpUrl = HttpUrl("http://localhost:6333")
    api_key: SecretStr | None = None
    prefix: str = "dam"
    visual_dimensions: PositiveInt = Field(default=512, description="Размерность CLIP")
    face_dimensions: PositiveInt = Field(default=128, description="Размерность SFace")


def create_qdrant_client(config: QdrantConfig) -> AsyncQdrantClient:
    api_key = config.api_key.get_secret_value() if config.api_key else None
    return AsyncQdrantClient(url=str(config.url), api_key=api_key, timeout=30)


_KEYWORD_FIELDS = ("asset_id", "version_id", "collection_id", "kind", "person_id")
_BOOL_FIELDS = ("current", "trashed", "confirmed")


async def _ensure_collection(client: AsyncQdrantClient, name: str, size: int) -> None:
    """Создаёт коллекцию; API и воркеры стартуют одновременно, поэтому «уже существует» — не ошибка."""

    if await client.collection_exists(name):
        return

    try:
        await client.create_collection(
            name, vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE)
        )
    except UnexpectedResponse as exc:
        if exc.status_code != HTTPStatus.CONFLICT:
            raise
        return

    for field in _KEYWORD_FIELDS:
        await client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)
    for field in _BOOL_FIELDS:
        await client.create_payload_index(name, field, models.PayloadSchemaType.BOOL)


def _match(key: str, value: Any) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _scope_filter(scope: SearchScope, *extra: models.Condition) -> models.Filter:
    must: list[models.Condition] = [_match("current", True), _match("trashed", False), *extra]

    if scope.collection_ids is not None:
        must.append(
            models.FieldCondition(
                key="collection_id", match=models.MatchAny(any=[str(cid) for cid in scope.collection_ids])
            )
        )
    if scope.kinds:
        must.append(
            models.FieldCondition(key="kind", match=models.MatchAny(any=[str(k) for k in scope.kinds]))
        )

    return models.Filter(must=must)


def _state_payload(state: AssetIndexState) -> dict[str, Any]:
    return {"collection_id": str(state.collection_id), "kind": str(state.kind), "trashed": state.trashed}


class _AssetIndex:
    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def _replace(self, version_id: UUID, points: list[models.PointStruct]) -> None:
        await self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[_match("version_id", str(version_id))])
            ),
        )
        if points:
            await self._client.upsert(self._collection, points=points)

    async def sync_asset(self, state: AssetIndexState) -> None:
        asset = _match("asset_id", str(state.asset_id))
        await self._client.set_payload(
            self._collection, payload=_state_payload(state), points=models.Filter(must=[asset])
        )
        await self._client.set_payload(
            self._collection, payload={"current": False}, points=models.Filter(must=[asset])
        )
        await self._client.set_payload(
            self._collection,
            payload={"current": True},
            points=models.Filter(must=[asset, _match("version_id", str(state.current_version_id))]),
        )

    async def delete_asset(self, asset_id: UUID) -> None:
        await self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[_match("asset_id", str(asset_id))])
            ),
        )


class QdrantVisualIndex(_AssetIndex, VisualIndex):
    def __init__(self, client: AsyncQdrantClient, config: QdrantConfig) -> None:
        super().__init__(client, f"{config.prefix}_visual")
        self._config = config

    async def ensure_collection(self) -> None:
        await _ensure_collection(self._client, self._collection, self._config.visual_dimensions)

    async def replace_version(self, state: AssetIndexState, points: Sequence[VisualPoint]) -> None:
        await self._replace(
            points[0].version_id if points else state.current_version_id,
            [
                models.PointStruct(
                    id=str(uuid.uuid5(point.version_id, str(point.timecode))),
                    vector=point.vector,
                    payload={
                        **_state_payload(state),
                        "asset_id": str(state.asset_id),
                        "version_id": str(point.version_id),
                        "current": point.version_id == state.current_version_id,
                        "timecode": point.timecode,
                    },
                )
                for point in points
            ],
        )

    async def search(
        self, vector: list[float], scope: SearchScope, *, limit: int, min_score: float
    ) -> list[VisualHit]:
        if scope.collection_ids == []:
            return []

        response = await self._client.query_points(
            self._collection,
            query=vector,
            query_filter=_scope_filter(scope),
            limit=limit,
            score_threshold=min_score,
            with_payload=["asset_id", "timecode"],
        )
        return [
            VisualHit(
                asset_id=UUID(point.payload["asset_id"]),
                score=point.score,
                timecode=point.payload.get("timecode"),
            )
            for point in response.points
            if point.payload
        ]


class QdrantFaceIndex(_AssetIndex, FaceIndex):
    def __init__(self, client: AsyncQdrantClient, config: QdrantConfig) -> None:
        super().__init__(client, f"{config.prefix}_faces")
        self._config = config

    async def ensure_collection(self) -> None:
        await _ensure_collection(self._client, self._collection, self._config.face_dimensions)

    async def replace_version(
        self, state: AssetIndexState, version_id: UUID, points: Sequence[FacePoint]
    ) -> None:
        await self._replace(
            version_id,
            [
                models.PointStruct(
                    id=str(point.face_id),
                    vector=point.vector,
                    payload={
                        **_state_payload(state),
                        "asset_id": str(state.asset_id),
                        "version_id": str(version_id),
                        "current": version_id == state.current_version_id,
                        "person_id": str(point.person_id) if point.person_id else None,
                        "confirmed": point.confirmed,
                    },
                )
                for point in points
            ],
        )

    async def search(
        self,
        vector: list[float],
        scope: SearchScope,
        *,
        limit: int,
        min_score: float,
        only_people: bool = False,
        only_unconfirmed: bool = False,
    ) -> list[FaceHit]:
        if scope.collection_ids == []:
            return []

        query_filter = _scope_filter(scope, *([_match("confirmed", False)] if only_unconfirmed else []))
        if only_people:
            query_filter.must_not = [models.IsEmptyCondition(is_empty=models.PayloadField(key="person_id"))]

        response = await self._client.query_points(
            self._collection,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=min_score,
            with_payload=["asset_id", "person_id"],
        )
        return [
            FaceHit(
                face_id=UUID(str(point.id)),
                asset_id=UUID(point.payload["asset_id"]),
                person_id=UUID(person) if (person := point.payload.get("person_id")) else None,
                score=point.score,
            )
            for point in response.points
            if point.payload
        ]

    async def get_vector(self, face_id: UUID) -> list[float] | None:
        points = await self._client.retrieve(self._collection, ids=[str(face_id)], with_vectors=True)
        if not points or points[0].vector is None:
            return None

        vector = points[0].vector
        # Коллекция с одним безымянным вектором: плоский список чисел
        return [value for value in vector if isinstance(value, float)] if isinstance(vector, list) else None

    async def set_person(self, face_ids: Sequence[UUID], person_id: UUID | None, *, confirmed: bool) -> None:
        if not face_ids:
            return

        await self._client.set_payload(
            self._collection,
            payload={"person_id": str(person_id) if person_id else None, "confirmed": confirmed},
            points=[str(face_id) for face_id in face_ids],
        )


__all__ = ["QdrantConfig", "QdrantFaceIndex", "QdrantVisualIndex", "create_qdrant_client"]

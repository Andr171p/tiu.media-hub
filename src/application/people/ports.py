from typing import Protocol

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from src.application.search.ports import AssetIndexState, SearchScope
from src.domain.common import Box


@dataclass(frozen=True, slots=True)
class DetectedFace:
    box: Box
    vector: list[float]
    score: float
    thumbnail: bytes
    """Квадратная миниатюра лица (WebP)."""


class FaceAnalyzer(Protocol):
    same_person_score: float
    """Порог сходства векторов, начиная с которого лица считаются одним человеком."""

    async def detect(self, image: bytes) -> list[DetectedFace]:
        """Лица на изображении с векторами для сравнения."""

    def similarity(self, first: Sequence[float], second: Sequence[float]) -> float: ...


@dataclass(frozen=True, slots=True)
class FacePoint:
    face_id: UUID
    vector: list[float]
    person_id: UUID | None
    confirmed: bool


@dataclass(frozen=True, slots=True)
class FaceHit:
    face_id: UUID
    asset_id: UUID
    person_id: UUID | None
    score: float


class FaceIndex(Protocol):
    async def replace_version(
        self, state: AssetIndexState, version_id: UUID, points: Sequence[FacePoint]
    ) -> None:
        """Заменяет лица версии (идемпотентно)."""

    async def search(
        self,
        vector: list[float],
        scope: SearchScope,
        *,
        limit: int,
        min_score: float,
        only_people: bool = False,
        only_unconfirmed: bool = False,
    ) -> list[FaceHit]: ...

    async def get_vector(self, face_id: UUID) -> list[float] | None: ...

    async def set_person(
        self, face_ids: Sequence[UUID], person_id: UUID | None, *, confirmed: bool
    ) -> None: ...

    async def sync_asset(self, state: AssetIndexState) -> None: ...

    async def delete_asset(self, asset_id: UUID) -> None: ...


__all__ = ["DetectedFace", "FaceAnalyzer", "FaceHit", "FaceIndex", "FacePoint"]

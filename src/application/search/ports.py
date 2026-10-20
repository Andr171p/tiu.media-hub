from typing import Protocol

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from src.domain.assets import AssetKind


class ClipEmbedder(Protocol):
    """Общее пространство изображений и текста (CLIP): поиск по описанию и по похожим фото."""

    text_match_score: float
    """Минимальное сходство текста и изображения, при котором результат считается найденным."""

    image_match_score: float
    """Минимальное сходство двух изображений."""

    async def embed_images(self, images: Sequence[bytes]) -> list[list[float]]: ...

    async def embed_text(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class AssetIndexState:
    """Состояние актива, от которого зависит видимость его векторов в поиске."""

    asset_id: UUID
    collection_id: UUID
    kind: AssetKind
    current_version_id: UUID
    trashed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualPoint:
    vector: list[float]
    version_id: UUID
    timecode: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchScope:
    collection_ids: Sequence[UUID] | None
    """``None`` — все коллекции."""

    kinds: Sequence[AssetKind] = ()


@dataclass(frozen=True, slots=True)
class VisualHit:
    asset_id: UUID
    score: float
    timecode: float | None


class VisualIndex(Protocol):
    """Векторы кадров текущих версий (изображение — один кадр, видео — выборка кадров)."""

    async def replace_version(self, state: AssetIndexState, points: Sequence[VisualPoint]) -> None:
        """Заменяет векторы версии (идемпотентно)."""

    async def search(
        self, vector: list[float], scope: SearchScope, *, limit: int, min_score: float
    ) -> list[VisualHit]: ...

    async def sync_asset(self, state: AssetIndexState) -> None:
        """Обновляет видимость векторов актива: текущая версия, коллекция, корзина."""

    async def delete_asset(self, asset_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class TextHit:
    asset_id: UUID
    rank: float
    snippet: str | None = None
    timecode: float | None = None
    """Совпадение в речи видео/аудио."""


class TextSearchRepository(Protocol):
    async def search(self, query: str, scope: SearchScope, *, limit: int) -> list[TextHit]:
        """Полнотекстовый поиск по названию, описаниям, тегам и расшифровке речи."""


__all__ = [
    "AssetIndexState",
    "ClipEmbedder",
    "SearchScope",
    "TextHit",
    "TextSearchRepository",
    "VisualHit",
    "VisualIndex",
    "VisualPoint",
]

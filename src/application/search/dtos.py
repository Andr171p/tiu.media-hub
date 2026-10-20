from enum import StrEnum
from uuid import UUID

from pydantic import Field

from src.application.assets.dtos import AssetSummary
from src.application.dtos import CamelModel
from src.domain.assets import AssetKind


class MatchSource(StrEnum):
    VISUAL = "visual"
    """Похоже по изображению (CLIP)."""

    TEXT = "text"
    """Название, описание, теги."""

    SPEECH = "speech"
    """Сказано в видео/аудио."""

    FACE = "face"


class SearchMatch(CamelModel):
    source: MatchSource
    timecode: float | None = Field(default=None, description="Момент в видео, секунды")
    snippet: str | None = Field(default=None, description="Фрагмент текста с совпадением")


class SearchHit(CamelModel):
    asset: AssetSummary
    score: float
    matches: list[SearchMatch]


class SearchFilters(CamelModel):
    collection_ids: list[UUID] = Field(default_factory=list, description="Пусто — все доступные")
    kinds: list[AssetKind] = Field(default_factory=list)
    limit: int = Field(default=60, ge=1, le=200)


class TextSearchDTO(SearchFilters):
    query: str = Field(min_length=1, max_length=500, examples=["студент получает диплом на сцене"])


class SearchResponse(CamelModel):
    items: list[SearchHit]

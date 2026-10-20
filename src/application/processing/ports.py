from typing import Protocol

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.domain.assets import AssetKind, RenditionKind, VersionMeta


class UnsupportedMediaError(Exception):
    """Файл повреждён или его формат не поддерживается: повтор обработки не поможет."""


@dataclass(frozen=True, slots=True)
class RenditionFile:
    kind: RenditionKind
    path: Path
    content_type: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class ProcessedMedia:
    meta: VersionMeta
    renditions: list[RenditionFile]


@dataclass(frozen=True, slots=True)
class Frame:
    """Кадр для анализа (JPEG). ``timecode`` — секунды для видео, ``None`` для изображения."""

    image: bytes
    timecode: float | None = None


class MediaProcessor(Protocol):
    async def process(self, source: Path, kind: AssetKind, workdir: Path) -> ProcessedMedia:
        """Метаданные и производные (миниатюра, превью, прокси)."""

    async def sample_frames(self, video: Path, *, max_frames: int) -> list[Frame]:
        """Равномерная выборка кадров видео."""


@dataclass(frozen=True, slots=True)
class Annotation:
    caption: str
    tags: list[str]


class ImageAnnotator(Protocol):
    async def annotate(self, frames: Sequence[Frame], *, kind: AssetKind) -> Annotation:
        """Описание и ключевые слова по кадрам (на русском)."""


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class Transcript:
    language: str | None
    segments: list[TranscriptSegment]

    @property
    def text(self) -> str:
        return " ".join(segment.text for segment in self.segments)


class Transcriber(Protocol):
    async def transcribe(self, media: Path) -> Transcript: ...


__all__ = [
    "Annotation",
    "Frame",
    "ImageAnnotator",
    "MediaProcessor",
    "ProcessedMedia",
    "RenditionFile",
    "Transcriber",
    "Transcript",
    "TranscriptSegment",
    "UnsupportedMediaError",
]

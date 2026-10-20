from typing import Literal

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from ddf.domain.exceptions import InvalidStateError, InvariantViolationError
from ddf.domain.models import AggregateRoot

from .common import Box


@dataclass(frozen=True, kw_only=True)
class Region(Box):
    """Отмеченная область изображения."""

    type: Literal["region"] = "region"


@dataclass(frozen=True, kw_only=True)
class TimeRange:
    """Момент или отрезок видео/аудио в секундах."""

    type: Literal["time"] = "time"
    start: float
    end: float | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or (self.end is not None and self.end < self.start):
            raise InvariantViolationError("Invalid time range.")


type Anchor = Region | TimeRange


@dataclass(kw_only=True)
class Comment(AggregateRoot):
    """Комментарий к версии актива. Обсуждение — корневой комментарий с ответами одного уровня."""

    asset_id: UUID
    version_id: UUID
    author_id: UUID
    text: str
    parent_id: UUID | None = None
    anchor: Anchor | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None

    @property
    def is_thread(self) -> bool:
        return self.parent_id is None

    def reply(self, *, author_id: UUID, text: str) -> Comment:
        if not self.is_thread:
            raise InvalidStateError("Replies are allowed only to a thread comment.")

        return Comment(
            asset_id=self.asset_id,
            version_id=self.version_id,
            author_id=author_id,
            text=text,
            parent_id=self.id,
        )

    def resolve(self, *, by: UUID) -> None:
        if not self.is_thread:
            raise InvalidStateError("Only a thread can be resolved.")

        if self.resolved_at is None:
            self.resolved_at = self.updated_at = datetime.now(UTC)
            self.resolved_by = by

    def reopen(self) -> None:
        self.resolved_at = self.resolved_by = None
        self.updated_at = datetime.now(UTC)

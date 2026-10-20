from typing import ClassVar

from dataclasses import dataclass
from uuid import UUID

from ddf.domain.events import Event
from ddf.domain.models import AggregateRoot, Entity

from .common import Box


@dataclass(frozen=True, kw_only=True)
class FaceAssigned(Event):
    """Лицо подписано вручную: похожие неподписанные лица можно распознать как этого человека."""

    event_type: ClassVar[str] = "people.face_assigned"

    face_id: UUID
    person_id: UUID | None


@dataclass(kw_only=True)
class Person(AggregateRoot):
    """Человек, которого система находит на фото и видео."""

    name: str
    description: str | None = None
    created_by: UUID


@dataclass(kw_only=True)
class Face(Entity):
    """
    Лицо на версии актива. Вектор лица хранится в векторном индексе под тем же ``id``.
    Для видео одно лицо объединяет появления человека в разных кадрах (``timecodes``).
    """

    asset_id: UUID
    version_id: UUID
    box: Box
    timecodes: tuple[float, ...] = ()
    person_id: UUID | None = None
    assigned_by: UUID | None = None
    """Кто подписал лицо; ``None`` — распознано автоматически."""

    @property
    def is_confirmed(self) -> bool:
        return self.assigned_by is not None

    def assign(self, person_id: UUID | None, *, by: UUID) -> None:
        """Ручная подпись (или снятие подписи) — автоматическое распознавание её не перезапишет."""

        self.person_id = person_id
        self.assigned_by = by if person_id is not None else None
        self.register_event(FaceAssigned(face_id=self.id, person_id=person_id))

    def match(self, person_id: UUID) -> bool:
        """Автоматическое распознавание: не трогает лица, подписанные вручную."""

        if self.is_confirmed or self.person_id == person_id:
            return False

        self.person_id = person_id
        return True

from collections.abc import Sequence
from uuid import UUID

from ddf.application.repositories import Repository

from src.domain.people import Face, Person


class PersonRepository(Repository[Person]):
    async def search(self, query: str | None, *, limit: int) -> Sequence[Person]:
        raise NotImplementedError


class FaceRepository(Repository[Face]):
    async def list_by_version(self, version_id: UUID) -> Sequence[Face]:
        raise NotImplementedError

    async def exists_for_version(self, version_id: UUID) -> bool:
        raise NotImplementedError

    async def first_confirmed(self, person_ids: Sequence[UUID]) -> dict[UUID, Face]:
        """Подписанное вручную лицо каждого человека: обложка в списке людей."""
        raise NotImplementedError

    async def unassign_person(self, person_id: UUID) -> list[UUID]:
        """Снимает подпись со всех лиц человека и возвращает их идентификаторы."""
        raise NotImplementedError


__all__ = ["FaceRepository", "PersonRepository"]

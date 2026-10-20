from collections.abc import Sequence
from uuid import UUID

from ddf.infra.database.sqlalchemy import SqlAlchemyRepository
from sqlalchemy import exists, select, update

from src.application.people.repositories import FaceRepository, PersonRepository
from src.domain.common import Box
from src.domain.people import Face, Person

from ..codec import from_json, to_json
from ..models import FaceOrm, PersonOrm


class PersonMapper:
    def to_model(self, entity: Person) -> PersonOrm:
        return PersonOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            name=entity.name,
            description=entity.description,
            created_by=entity.created_by,
        )

    def from_model(self, model: PersonOrm) -> Person:
        return Person(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            name=model.name,
            description=model.description,
            created_by=model.created_by,
        )


class FaceMapper:
    def to_model(self, entity: Face) -> FaceOrm:
        return FaceOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            asset_id=entity.asset_id,
            version_id=entity.version_id,
            box=to_json(Box, entity.box),
            timecodes=list(entity.timecodes),
            person_id=entity.person_id,
            assigned_by=entity.assigned_by,
        )

    def from_model(self, model: FaceOrm) -> Face:
        return Face(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            asset_id=model.asset_id,
            version_id=model.version_id,
            box=from_json(Box, model.box),
            timecodes=tuple(model.timecodes),
            person_id=model.person_id,
            assigned_by=model.assigned_by,
        )


class SqlAlchemyPersonRepository(SqlAlchemyRepository[Person, PersonOrm], PersonRepository):
    model = PersonOrm
    data_mapper = PersonMapper()

    async def search(self, query: str | None, *, limit: int) -> Sequence[Person]:
        stmt = select(PersonOrm).order_by(PersonOrm.name, PersonOrm.id).limit(limit)
        if query:
            stmt = stmt.where(PersonOrm.name.ilike(f"%{query.strip()}%"))

        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


class SqlAlchemyFaceRepository(SqlAlchemyRepository[Face, FaceOrm], FaceRepository):
    model = FaceOrm
    data_mapper = FaceMapper()

    async def list_by_version(self, version_id: UUID) -> Sequence[Face]:
        stmt = select(FaceOrm).where(FaceOrm.version_id == version_id).order_by(FaceOrm.id)
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]

    async def exists_for_version(self, version_id: UUID) -> bool:
        return bool(await self._session.scalar(select(exists().where(FaceOrm.version_id == version_id))))

    async def first_confirmed(self, person_ids: Sequence[UUID]) -> dict[UUID, Face]:
        if not person_ids:
            return {}

        stmt = (
            select(FaceOrm)
            .where(FaceOrm.person_id.in_(person_ids), FaceOrm.assigned_by.is_not(None))
            .distinct(FaceOrm.person_id)
            .order_by(FaceOrm.person_id, FaceOrm.updated_at)
        )
        faces = [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]
        return {face.person_id: face for face in faces if face.person_id}

    async def unassign_person(self, person_id: UUID) -> list[UUID]:
        stmt = (
            update(FaceOrm)
            .where(FaceOrm.person_id == person_id)
            .values(person_id=None, assigned_by=None)
            .returning(FaceOrm.id)
        )
        return list(await self._session.scalars(stmt))

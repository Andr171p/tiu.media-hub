from collections.abc import Sequence

from ddf.infra.database.sqlalchemy import SqlAlchemyRepository
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from src.application.users import UserRepository
from src.domain.users import User

from ..models import UserOrm


class UserMapper:
    def to_model(self, entity: User) -> UserOrm:
        return UserOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            username=entity.username,
            email=entity.email,
            full_name=entity.full_name,
        )

    def from_model(self, model: UserOrm) -> User:
        return User(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            username=model.username,
            email=model.email,
            full_name=model.full_name,
        )


class SqlAlchemyUserRepository(SqlAlchemyRepository[User, UserOrm], UserRepository):
    model = UserOrm
    data_mapper = UserMapper()

    async def save_profile(self, user: User) -> None:
        values = {"username": user.username, "email": user.email, "full_name": user.full_name}
        stmt = (
            insert(UserOrm)
            .values(id=user.id, **values)
            .on_conflict_do_update(index_elements=[UserOrm.id], set_={**values, "updated_at": func.now()})
        )
        await self._session.execute(stmt)

    async def search(self, query: str, *, limit: int) -> Sequence[User]:
        pattern = f"%{query.strip()}%"
        stmt = (
            select(UserOrm)
            .where(
                or_(
                    UserOrm.full_name.ilike(pattern),
                    UserOrm.username.ilike(pattern),
                    UserOrm.email.ilike(pattern),
                )
            )
            .order_by(UserOrm.full_name, UserOrm.id)
            .limit(limit)
        )
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]

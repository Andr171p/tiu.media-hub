from collections.abc import Sequence
from uuid import UUID

from ddf.application.repositories import Repository
from ddf.application.uow import UnitOfWork
from pydantic import Field

from src.domain.users import User

from .auth import AuthUser
from .dtos import CamelModel


class UserRepository(Repository[User]):
    async def save_profile(self, user: User) -> None:
        """Создаёт или обновляет профиль (upsert)."""
        raise NotImplementedError

    async def search(self, query: str, *, limit: int) -> Sequence[User]:
        raise NotImplementedError


class UserResponse(CamelModel):
    id: UUID
    username: str | None
    email: str | None
    full_name: str | None
    display_name: str


class MeResponse(UserResponse):
    is_admin: bool = Field(description="Глобальная роль администратора из Keycloak")


async def sync_profile(auth: AuthUser, *, user_repository: UserRepository, uow: UnitOfWork) -> None:
    """Сохраняет профиль из токена: по нему ищут участников и показывают авторов."""

    await user_repository.save_profile(
        User(
            id=auth.user.id,
            username=auth.user.username,
            email=auth.user.email,
            full_name=auth.user.full_name,
        )
    )
    await uow.commit()


def get_me(auth: AuthUser) -> MeResponse:
    user = User(
        id=auth.user.id, username=auth.user.username, email=auth.user.email, full_name=auth.user.full_name
    )
    return MeResponse(**UserResponse.model_validate(user).model_dump(), is_admin=auth.is_admin)


async def search_users(query: str, *, user_repository: UserRepository, limit: int = 20) -> list[UserResponse]:
    return [UserResponse.model_validate(user) for user in await user_repository.search(query, limit=limit)]


async def get_users(ids: Sequence[UUID], *, user_repository: UserRepository) -> list[UserResponse]:
    return [UserResponse.model_validate(user) for user in await user_repository.get_by_ids(ids)]


__all__ = [
    "MeResponse",
    "UserRepository",
    "UserResponse",
    "get_me",
    "get_users",
    "search_users",
    "sync_profile",
]

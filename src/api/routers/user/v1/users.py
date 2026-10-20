from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Query

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.repositories import UserRepositoryDep
from src.application.users import MeResponse, UserResponse, get_me, get_users, search_users

router = APIRouter(tags=["Пользователи"])


@router.get("/me", summary="Текущий пользователь")
async def me(auth: CurrentUser) -> MeResponse:
    return get_me(auth)


@router.get(
    "/users",
    summary="Поиск сотрудников",
    description="По имени, логину или email (кто уже входил в систему).",
)
async def find_users(
    _: CurrentUser,
    user_repository: UserRepositoryDep,
    query: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ids: Annotated[list[UUID] | None, Query(max_length=200)] = None,
) -> list[UserResponse]:
    if ids:
        return await get_users(ids, user_repository=user_repository)

    return await search_users(query or "", user_repository=user_repository)

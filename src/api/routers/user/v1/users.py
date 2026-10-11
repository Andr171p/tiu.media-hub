from typing import Annotated

from fastapi import APIRouter, Query

from src.api.dependencies import CurrentUser, DBSession
from src.modules import users
from src.modules.users import CurrentUserResponse, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Текущий пользователь",
    description="Обновляет локальный профиль данными из токена.",
)
async def get_me(db: DBSession, auth: CurrentUser) -> CurrentUserResponse:
    profile = await users.sync_profile(db, auth.user)
    await db.commit()

    return CurrentUserResponse(
        **UserResponse.model_validate(profile).model_dump(),
        roles=sorted(auth.user.roles),
        is_admin=auth.is_admin,
    )


@router.get("", summary="Найти пользователей", description="Среди тех, кто хотя бы раз входил в DAM.")
async def search_users(
    db: DBSession,
    _: CurrentUser,
    query: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[UserResponse]:
    return [UserResponse.model_validate(user) for user in await users.search_users(db, query)]

from fastapi import APIRouter

from src.core.auth.models import User
from src.modules.auth import CurrentUser

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", summary="Получить текущего пользователя")
async def get_me(user: CurrentUser) -> User:
    return user

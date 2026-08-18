from fastapi import APIRouter, status

from src.core.auth.models import User
from src.modules.auth.dependencies import CurrentUser

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    path="/me",
    status_code=status.HTTP_200_OK,
    response_model=User,
    summary="Получить текущего пользователя"
)
async def get_me(current_user: CurrentUser) -> User:
    return current_user

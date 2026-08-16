from fastapi import APIRouter

from . import users

router = APIRouter(prefix="/v1")

router.include_router(users.router)

__all__ = ["router"]

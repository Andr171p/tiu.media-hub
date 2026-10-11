from fastapi import APIRouter

from . import admin, client, user

router = APIRouter(prefix="/api")

router.include_router(user.router)
router.include_router(admin.router)
router.include_router(client.router)

__all__ = ["router"]

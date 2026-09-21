from fastapi import APIRouter

from . import assets, collections, media, users

router = APIRouter(prefix="/v1")

router.include_router(assets.router)
router.include_router(collections.router)
router.include_router(media.router)
router.include_router(users.router)

__all__ = ["router"]

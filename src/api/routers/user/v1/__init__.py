from fastapi import APIRouter

from . import assets, collections, members, search, tags, uploads, users, versions

router = APIRouter(prefix="/v1")

router.include_router(users.router)
router.include_router(collections.router)
router.include_router(members.router)
router.include_router(uploads.router)
router.include_router(assets.router)
router.include_router(versions.router)
router.include_router(tags.router)
router.include_router(search.router)

__all__ = ["router"]

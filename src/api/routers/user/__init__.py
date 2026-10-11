from fastapi import APIRouter

from . import v1

router = APIRouter(prefix="/user")

router.include_router(v1.router)

__all__ = ["router"]

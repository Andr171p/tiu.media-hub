from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_admin

from . import maintenance, tags

router = APIRouter(prefix="/v1", dependencies=[Depends(get_current_admin)])

router.include_router(tags.router)
router.include_router(maintenance.router)

__all__ = ["router"]

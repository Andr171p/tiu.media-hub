"""API для доверенных сервисов (OAuth Client Credentials, роль ``assets:read``): только чтение."""

from fastapi import APIRouter, Depends

from src.api.dependencies.auth import get_current_client

from . import assets, collections

router = APIRouter(prefix="/v1", dependencies=[Depends(get_current_client)])

router.include_router(collections.router)
router.include_router(assets.router)

__all__ = ["router"]

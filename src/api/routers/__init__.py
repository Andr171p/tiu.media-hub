"""
Маршруты по потребителям:

* ``/api/v1`` — пользователи (фронт медиатеки);
* ``/api/admin/v1`` — администрирование;
* ``/api/service/v1`` — сервисы (Client Credentials);
* ``/api/public/v1`` — посетители порталов.
"""

from fastapi import APIRouter

from .admin.v1 import versions as admin_versions
from .public.v1 import portals as public_portals
from .service.v1 import assets as service_assets
from .user.v1 import assets, collections, comments, people, portals, search, selections, users

router = APIRouter()

for module in (users, collections, assets, comments, people, search, selections, portals):
    router.include_router(module.router, prefix="/v1")

router.include_router(admin_versions.router, prefix="/admin/v1")
router.include_router(service_assets.router, prefix="/service/v1")
router.include_router(public_portals.router, prefix="/public/v1")

__all__ = ["router"]

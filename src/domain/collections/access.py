from enum import StrEnum
from uuid import UUID

from .models import Collection, CollectionRole, Visibility


class Permission(StrEnum):
    READ = "read"
    """Просмотр, скачивание, комментарии."""

    WRITE = "write"
    """Загрузка и правка активов."""

    MANAGE = "manage"
    """Участники и настройки коллекции."""

    OWN = "own"
    """Удаление коллекции."""


_ROLE_PERMISSIONS: dict[CollectionRole, frozenset[Permission]] = {
    CollectionRole.VIEWER: frozenset({Permission.READ}),
    CollectionRole.EDITOR: frozenset({Permission.READ, Permission.WRITE}),
    CollectionRole.MANAGER: frozenset({Permission.READ, Permission.WRITE, Permission.MANAGE}),
}

ALL_PERMISSIONS = frozenset(Permission)


def resolve_permissions(
    collection: Collection,
    *,
    user_id: UUID,
    role: CollectionRole | None,
    is_admin: bool = False,
) -> frozenset[Permission]:
    """Права пользователя в коллекции: владелец и администратор могут всё, остальные — по роли."""

    if is_admin or collection.owner_id == user_id:
        return ALL_PERMISSIONS

    permissions = _ROLE_PERMISSIONS[role] if role is not None else frozenset()

    if collection.visibility is Visibility.INTERNAL:
        permissions |= {Permission.READ}

    return permissions

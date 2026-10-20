from dataclasses import dataclass
from uuid import UUID

from ddf.application.exceptions import NotFoundError

from src.application.auth import AuthUser, PermissionDeniedError
from src.domain.collections import Collection, CollectionRole, Permission, resolve_permissions

from .repositories import CollectionRepository


@dataclass(frozen=True, slots=True)
class CollectionAccess:
    collection: Collection
    role: CollectionRole | None
    permissions: frozenset[Permission]


async def get_collection_access(
    collection_id: UUID,
    auth: AuthUser,
    permission: Permission = Permission.READ,
    *,
    collection_repository: CollectionRepository,
) -> CollectionAccess:
    """Коллекция с правами пользователя. Без права чтения коллекция «не существует» (404)."""

    not_found = NotFoundError(f"Collection with ID {collection_id} not found.")

    if (collection := await collection_repository.read(collection_id)) is None:
        raise not_found

    role = await collection_repository.get_role(collection_id, auth.user_id)
    permissions = resolve_permissions(collection, user_id=auth.user_id, role=role, is_admin=auth.is_admin)

    if Permission.READ not in permissions:
        raise not_found

    if permission not in permissions:
        raise PermissionDeniedError(f"Permission {permission!r} required for collection {collection_id}.")

    return CollectionAccess(collection=collection, role=role, permissions=permissions)


async def readable_collection_ids(
    auth: AuthUser, *, collection_repository: CollectionRepository
) -> list[UUID] | None:
    """Коллекции, доступные на чтение; ``None`` — без ограничений (администратор)."""

    if auth.is_admin:
        return None

    return await collection_repository.readable_ids(auth.user_id)


__all__ = ["CollectionAccess", "get_collection_access", "readable_collection_ids"]

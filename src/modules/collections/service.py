from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.auth import AuthUser
from src.core.common.exceptions import InvalidDataError, NotFoundError
from src.modules.media import get_owned_object
from src.modules.users import UserResponse, sync_profile

from .access import Action, CollectionAccess, CollectionRole, resolve_role
from .models import Collection, CollectionMember, MemberRole, Visibility
from .schemas import (
    CollectionFilters,
    CollectionResponse,
    CollectionScope,
    CollectionStats,
    CreateCollectionDTO,
    UpdateCollectionDTO,
)
from .settings import CollectionSettings, ImageWatermark


def _active_collections() -> Select[tuple[Collection]]:
    return select(Collection).options(selectinload(Collection.owner)).where(Collection.deleted_at.is_(None))


async def _member_role(session: AsyncSession, collection_id: UUID, user_id: UUID) -> MemberRole | None:
    return await session.scalar(
        select(CollectionMember.role).where(
            CollectionMember.collection_id == collection_id,
            CollectionMember.user_id == user_id,
        ),
    )


async def get_access(
    session: AsyncSession,
    collection_id: UUID,
    user: AuthUser,
    action: Action = Action.VIEW,
) -> CollectionAccess:
    """Коллекция и права пользователя в ней. Недоступная приватная коллекция неотличима от несуществующей."""

    collection = await session.scalar(_active_collections().where(Collection.id == collection_id))
    if collection is None:
        raise NotFoundError("Collection not found.")

    role = resolve_role(collection, user, await _member_role(session, collection.id, user.user.id))
    if role is None:
        raise NotFoundError("Collection not found.")

    access = CollectionAccess(collection, role)
    access.require(action)
    return access


async def get_collection(session: AsyncSession, collection_id: UUID) -> Collection:
    """Коллекция без проверки прав: для доверенных сервисов и фоновых задач."""

    if (
        collection := await session.scalar(_active_collections().where(Collection.id == collection_id))
    ) is None:
        raise NotFoundError("Collection not found.")
    return collection


def _visible_condition(user: AuthUser):
    user_id = user.user.id
    return or_(
        Collection.visibility == Visibility.PUBLIC,
        Collection.owner_id == user_id,
        CollectionMember.id.is_not(None),
    )


async def list_collections(
    session: AsyncSession,
    user: AuthUser,
    filters: CollectionFilters,
) -> tuple[list[CollectionAccess], int]:
    user_id = user.user.id

    stmt = (
        _active_collections()
        .add_columns(CollectionMember.role)
        .outerjoin(
            CollectionMember,
            and_(
                CollectionMember.collection_id == Collection.id,
                CollectionMember.user_id == user_id,
            ),
        )
    )

    match filters.scope:
        case CollectionScope.MINE:
            stmt = stmt.where(or_(Collection.owner_id == user_id, CollectionMember.id.is_not(None)))
        case CollectionScope.PUBLIC:
            stmt = stmt.where(Collection.visibility == Visibility.PUBLIC)
        case CollectionScope.ALL if not user.is_admin:
            stmt = stmt.where(_visible_condition(user))

    if filters.query:
        stmt = stmt.where(Collection.name.ilike(f"%{filters.query.strip()}%"))

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = await session.execute(
        stmt.order_by(Collection.updated_at.desc()).limit(filters.limit).offset(filters.offset),
    )

    accesses = []
    for collection, member_role in rows.tuples():
        if (role := resolve_role(collection, user, member_role)) is not None:
            accesses.append(CollectionAccess(collection, role))

    return accesses, total


async def get_accesses(
    session: AsyncSession,
    collection_ids: Iterable[UUID],
    user: AuthUser,
) -> dict[UUID, CollectionAccess]:
    """Права пользователя сразу в нескольких коллекциях (выдача поиска). Недоступные пропускаются."""

    if not (ids := set(collection_ids)):
        return {}

    rows = await session.execute(
        _active_collections()
        .add_columns(CollectionMember.role)
        .outerjoin(
            CollectionMember,
            and_(
                CollectionMember.collection_id == Collection.id,
                CollectionMember.user_id == user.user.id,
            ),
        )
        .where(Collection.id.in_(ids)),
    )
    return {
        collection.id: CollectionAccess(collection, role)
        for collection, member_role in rows.tuples()
        if (role := resolve_role(collection, user, member_role)) is not None
    }


async def get_collections(session: AsyncSession, collection_ids: Iterable[UUID]) -> dict[UUID, Collection]:
    if not (ids := set(collection_ids)):
        return {}
    return {
        collection.id: collection
        for collection in await session.scalars(_active_collections().where(Collection.id.in_(ids)))
    }


async def accessible_collection_ids(session: AsyncSession, user: AuthUser) -> set[UUID] | None:
    """Коллекции, которые пользователь может просматривать. ``None`` — без ограничений (администратор)."""

    if user.is_admin:
        return None

    stmt = (
        select(Collection.id)
        .outerjoin(
            CollectionMember,
            and_(
                CollectionMember.collection_id == Collection.id,
                CollectionMember.user_id == user.user.id,
            ),
        )
        .where(Collection.deleted_at.is_(None), _visible_condition(user))
    )
    return set((await session.scalars(stmt)).all())


async def create_collection(
    session: AsyncSession, user: AuthUser, dto: CreateCollectionDTO
) -> CollectionAccess:
    owner = await sync_profile(session, user.user)

    collection = Collection(
        name=dto.name,
        description=dto.description,
        visibility=dto.visibility,
        owner_id=owner.id,
        settings=CollectionSettings(),
    )
    session.add(collection)
    await session.flush()

    collection.owner = owner
    return CollectionAccess(collection, CollectionRole.OWNER)


async def update_collection(access: CollectionAccess, dto: UpdateCollectionDTO) -> Collection:
    changes = dto.model_dump(exclude_unset=True)

    access.require(Action.MANAGE if "visibility" in changes else Action.MODERATE)
    if changes.get("name", ...) is None:
        raise InvalidDataError("Collection name cannot be empty.")

    for field, value in changes.items():
        setattr(access.collection, field, value)
    return access.collection


async def update_settings(
    session: AsyncSession,
    access: CollectionAccess,
    settings: CollectionSettings,
    user: AuthUser,
) -> bool:
    """Заменяет настройки коллекции. Возвращает ``True``, если изменился водяной знак."""

    access.require(Action.MODERATE)
    collection = access.collection

    watermark = settings.watermark
    current = collection.settings.watermark
    if isinstance(watermark, ImageWatermark) and not (
        isinstance(current, ImageWatermark) and current.object_id == watermark.object_id
    ):
        obj = await get_owned_object(session, watermark.object_id, user_id=user.user.id)
        if not obj.content_type.startswith("image/"):
            raise InvalidDataError("Watermark must be an image.")

    collection.settings = settings
    return watermark != current


async def delete_collection(access: CollectionAccess) -> None:
    access.require(Action.MANAGE)
    access.collection.deleted_at = datetime.now(UTC)


def to_collection_response(
    access: CollectionAccess, stats: CollectionStats | None = None
) -> CollectionResponse:
    collection = access.collection
    return CollectionResponse(
        id=collection.id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        name=collection.name,
        description=collection.description,
        visibility=collection.visibility,
        owner=UserResponse.model_validate(collection.owner),
        settings=collection.settings,
        role=access.role.label,
        permissions=access.permissions,
        stats=stats or CollectionStats(),
    )


__all__ = [
    "accessible_collection_ids",
    "create_collection",
    "delete_collection",
    "get_access",
    "get_accesses",
    "get_collection",
    "get_collections",
    "list_collections",
    "to_collection_response",
    "update_collection",
    "update_settings",
]

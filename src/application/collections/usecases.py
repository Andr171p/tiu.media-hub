from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.uow import UnitOfWork
from ddf.domain.exceptions import InvalidStateError, InvariantViolationError
from ddf.domain.utils import apply_changes

from src.application.auth import AuthUser
from src.application.users import UserRepository
from src.domain.collections import (
    ALL_PERMISSIONS,
    Collection,
    CollectionMember,
    Permission,
    resolve_permissions,
)

from .access import get_collection_access
from .dtos import (
    CollectionResponse,
    CreateCollectionDTO,
    MemberDTO,
    MemberResponse,
    UpdateCollectionDTO,
)
from .repositories import CollectionMemberRepository, CollectionRepository


async def create_collection(
    dto: CreateCollectionDTO,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> CollectionResponse:
    collection = Collection(
        name=dto.name,
        description=dto.description,
        owner_id=auth.user_id,
        visibility=dto.visibility,
        upload_policy=dto.upload_policy.to_domain(),
        metadata_schema=tuple(item.to_domain() for item in dto.metadata_schema),
    )
    await collection_repository.create(collection)
    await uow.commit()

    return CollectionResponse.build(collection, role=None, permissions=ALL_PERMISSIONS, asset_count=0)


async def list_collections(
    auth: AuthUser, *, collection_repository: CollectionRepository
) -> list[CollectionResponse]:
    items = await collection_repository.list_visible(None if auth.is_admin else auth.user_id)

    return [
        CollectionResponse.build(
            item.collection,
            role=item.role,
            permissions=resolve_permissions(
                item.collection, user_id=auth.user_id, role=item.role, is_admin=auth.is_admin
            ),
            asset_count=item.asset_count,
        )
        for item in items
    ]


async def get_collection(
    collection_id: UUID, auth: AuthUser, *, collection_repository: CollectionRepository
) -> CollectionResponse:
    access = await get_collection_access(collection_id, auth, collection_repository=collection_repository)
    return CollectionResponse.build(access.collection, role=access.role, permissions=access.permissions)


async def update_collection(
    collection_id: UUID,
    dto: UpdateCollectionDTO,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> CollectionResponse:
    access = await get_collection_access(
        collection_id, auth, Permission.MANAGE, collection_repository=collection_repository
    )
    collection = access.collection

    apply_changes(
        collection,
        name=dto.name,
        description=dto.description,
        visibility=dto.visibility,
        upload_policy=dto.upload_policy.to_domain() if dto.upload_policy else None,
    )
    if dto.metadata_schema is not None:
        collection.change_metadata_schema(tuple(item.to_domain() for item in dto.metadata_schema))

    await collection_repository.update(collection)
    await uow.commit()

    return CollectionResponse.build(collection, role=access.role, permissions=access.permissions)


async def delete_collection(
    collection_id: UUID,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    uow: UnitOfWork,
) -> None:
    """Удалять можно только пустую коллекцию: активы сначала переносят или удаляют из корзины."""

    await get_collection_access(
        collection_id, auth, Permission.OWN, collection_repository=collection_repository
    )

    if await collection_repository.count_assets(collection_id):
        raise InvalidStateError("Collection is not empty.")

    await collection_repository.delete(collection_id)
    await uow.commit()


async def list_members(
    collection_id: UUID,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    member_repository: CollectionMemberRepository,
    user_repository: UserRepository,
) -> list[MemberResponse]:
    await get_collection_access(collection_id, auth, collection_repository=collection_repository)

    members = await member_repository.list_members(collection_id)
    users = {user.id: user for user in await user_repository.get_by_ids([m.user_id for m in members])}

    return [
        MemberResponse(
            user_id=member.user_id,
            role=member.role,
            display_name=users[member.user_id].display_name if member.user_id in users else None,
            email=users[member.user_id].email if member.user_id in users else None,
        )
        for member in members
    ]


async def set_member(
    collection_id: UUID,
    dto: MemberDTO,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    member_repository: CollectionMemberRepository,
    uow: UnitOfWork,
) -> None:
    """Добавляет участника или меняет его роль."""

    access = await get_collection_access(
        collection_id, auth, Permission.MANAGE, collection_repository=collection_repository
    )
    if dto.user_id == access.collection.owner_id:
        raise InvariantViolationError("Owner has full access and cannot be a member.")

    member = await member_repository.get_member(collection_id, dto.user_id)

    if member is None:
        await member_repository.create(
            CollectionMember(collection_id=collection_id, user_id=dto.user_id, role=dto.role)
        )
    else:
        apply_changes(member, role=dto.role)
        await member_repository.update(member)

    await uow.commit()


async def remove_member(
    collection_id: UUID,
    user_id: UUID,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    member_repository: CollectionMemberRepository,
    uow: UnitOfWork,
) -> None:
    """Участник может выйти сам, остальных удаляет менеджер."""

    permission = Permission.READ if user_id == auth.user_id else Permission.MANAGE
    await get_collection_access(collection_id, auth, permission, collection_repository=collection_repository)

    if (member := await member_repository.get_member(collection_id, user_id)) is None:
        raise NotFoundError(f"Member {user_id} not found.")

    await member_repository.delete(member.id)
    await uow.commit()

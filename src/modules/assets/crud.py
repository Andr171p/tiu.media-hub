from typing import Any

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.authorization import is_asset_author
from src.core.assets.dtos import CreateAssetDTO, UpdateAssetDTO
from src.core.assets.models import Asset
from src.core.auth.models import User
from src.core.collections.authorization import has_role, is_collection_owner
from src.core.collections.models import Collection, CollectionMember, MemberRole
from src.core.common.crud import Crud
from src.modules.collections.crud import get_collection_member


@dataclass(frozen=True, slots=True)
class CreateAssetOptions:
    collection: Collection
    user: User


@dataclass(frozen=True, slots=True)
class UpdateAssetOptions:
    collection: Collection
    user: User


async def _get_member_or_403(
    session: AsyncSession,
    collection: Collection,
    user: User,
) -> CollectionMember:
    if (member := await get_collection_member(session, collection.id, user.id)) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this collection.",
        )

    return member


async def _authorize_asset_create(
    session: AsyncSession,
    collection: Collection,
    user: User,
) -> None:
    """Поверяет права на создание медиа актива."""

    if is_collection_owner(collection, user.id):
        return

    member = await _get_member_or_403(session, collection, user)

    if not has_role(member, MemberRole.CONTRIBUTOR, MemberRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to modify assets in this collection.",
        )


async def _authorize_asset_update(
    session: AsyncSession,
    asset: Asset,
    collection: Collection,
    user: User,
) -> None:
    """Проверяет права на обновление медиа актива."""

    if is_collection_owner(collection, user) or is_asset_author(asset, user):
        return

    member = await _get_member_or_403(session, collection, user)

    if not has_role(member, MemberRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this asset.",
        )

    return


async def create_wrapper(
    session: AsyncSession,
    func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
    dto: CreateAssetDTO,
    options: CreateAssetOptions | None = None,
) -> Asset:
    if options is None:
        raise ValueError("Options required for asset creation.")

    await _authorize_asset_create(session, options.collection, options.user)

    return await func(
        {"collection_id": options.collection.id, "author_id": options.user.id},
    )


async def update_wrapper(
    session: AsyncSession,
    func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
    asset: Asset,
    dto: UpdateAssetDTO,
    options: UpdateAssetOptions | None = None,
) -> Asset:
    if options is None:
        raise ValueError("Options required for asset update.")

    if asset.collection_id != options.collection.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset does not belong to this collection.",
        )

    await _authorize_asset_update(
        session,
        asset=asset,
        collection=options.collection,
        user=options.collection,
    )

    return await func({})


crud = Crud[
    Asset,
    CreateAssetDTO,
    UpdateAssetDTO,
    CreateAssetOptions,
    UpdateAssetOptions,
    None,
    None,
](Asset, create_wrapper=create_wrapper, update_wrapper=update_wrapper)

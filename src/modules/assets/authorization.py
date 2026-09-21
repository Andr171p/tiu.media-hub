from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.models import Asset
from src.core.auth.models import User
from src.core.collections.authorization import has_role, is_collection_owner
from src.core.collections.models import Collection, MemberRole
from src.modules.collections.crud import get_collection_member


def _is_asset_author(asset: Asset, user: User) -> bool:
    return asset.author_id == user.id


async def can_create_asset(session: AsyncSession, collection: Collection, user: User) -> bool:
    """Может ли пользователь создать медиа-актив."""

    if is_collection_owner(collection, user):
        return True

    if (member := await get_collection_member(session, collection.id, user.id)) is None:
        return False

    return has_role(member, MemberRole.CONTRIBUTOR, MemberRole.MANAGER)


async def can_update_asset(
    session: AsyncSession,
    collection: Collection,
    asset: Asset,
    user: User,
) -> bool:
    """Может ли пользователь редактировать медиа-актив."""

    if is_collection_owner(collection, user) or _is_asset_author(asset, user):
        return True

    if (member := await get_collection_member(session, collection.id, user.id)) is None:
        return False

    return has_role(member, MemberRole.MANAGER)

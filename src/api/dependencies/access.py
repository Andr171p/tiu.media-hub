"""Ресурс из пути запроса вместе с правами текущего пользователя."""

from typing import Annotated

from uuid import UUID

from fastapi import Depends

from src.modules import assets, collections
from src.modules.assets import AssetContext
from src.modules.collections import CollectionAccess

from .auth import CurrentUser
from .database import DBSession


async def get_collection_access(collection_id: UUID, db: DBSession, user: CurrentUser) -> CollectionAccess:
    return await collections.get_access(db, collection_id, user)


async def get_asset_context(asset_id: UUID, db: DBSession, user: CurrentUser) -> AssetContext:
    return await assets.get_context(db, asset_id, user)


CollectionAccessDep = Annotated[CollectionAccess, Depends(get_collection_access)]
AssetContextDep = Annotated[AssetContext, Depends(get_asset_context)]

__all__ = ["AssetContextDep", "CollectionAccessDep"]

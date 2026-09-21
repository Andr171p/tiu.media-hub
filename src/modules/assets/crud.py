from typing import Any

from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.custom_meta_validation import validate_custom_meta
from src.core.assets.dtos import CreateAssetDTO, CreateAssetVersionDTO, UpdateAssetDTO
from src.core.assets.models import Asset, AssetStatus, AssetVersion
from src.core.auth.models import User
from src.core.common.crud import Crud
from src.core.media.crud import get_user_object
from src.modules.collections.crud import crud as collection_crud

from .authorization import can_create_asset, can_update_asset
from .versioning import get_next_asset_version_number


async def create_wrapper(
    session: AsyncSession,
    func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
    dto: CreateAssetDTO,
    creator: User | None = None,
) -> Asset:
    """Логика создания медиа-актива с его первой версией."""

    if creator is None:
        raise ValueError("Options required for asset creation.")

    collection_id = dto.collection_id
    if (collection := await collection_crud.read(session, collection_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with ID {collection_id!r} not found.",
        )

    if not await can_create_asset(session, collection, creator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create assets.",
        )

    custom_meta_schema = collection.settings.custom_meta_schema
    validate_custom_meta(custom_meta_schema, dto.custom_meta)

    asset = await func({"author_id": creator.id})

    version = AssetVersion(
        asset_id=asset.id,
        object_id=dto.object_id,
        number=1,
        original_filename=dto.original_filename,
    )
    session.add(version)
    await session.flush()

    return asset


async def update_wrapper(
    session: AsyncSession,
    func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
    asset: Asset,
    dto: UpdateAssetDTO,
    updator: User | None = None,
) -> Asset:
    if updator is None:
        raise ValueError("Options required for asset update.")

    collection_id = dto.collection_id
    if (collection := await collection_crud.read(session, collection_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with ID {collection_id!r} not found.",
        )

    if asset.collection_id != collection.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset does not belong to this collection.",
        )

    if not await can_update_asset(session, collection, asset, updator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update asset.",
        )

    payload = dto.model_dump(exclude={"collectionId"})
    return await func({**payload})


crud = Crud[
    Asset,
    CreateAssetDTO,
    UpdateAssetDTO,
    User,
    None,
    User,
    None,
](Asset, create_wrapper=create_wrapper, update_wrapper=update_wrapper)


async def _get_asset_for_update(session: AsyncSession, asset_id: UUID) -> Asset | None:
    """Получение ``Asset`` с блокировкой."""

    stmt = select(Asset).where(Asset.id == asset_id)
    return await session.scalar(stmt)


async def _validate_asset_version_uniqueness(
    session: AsyncSession,
    asset_id: UUID,
    obj_id: UUID,
) -> None:
    """Проверяет, что объект ещё не привязан к данному медиа-активу как версия."""

    stmt = select(AssetVersion).where(
        AssetVersion.asset_id == asset_id,
        AssetVersion.object_id == obj_id,
    )

    if await session.scalar(stmt) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Object with ID {obj_id!r} is already used by an asset version."
        )


async def create_asset_version(
    session: AsyncSession,
    asset_id: UUID,
    dto: CreateAssetVersionDTO,
    creator: User,
) -> AssetVersion:
    """Создание версии медиа-актива."""

    if (asset := await _get_asset_for_update(session, asset_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id!r} not found.",
        )

    collection_id = asset.collection_id
    if (collection := await collection_crud.read(session, collection_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with ID {collection_id!r} not found.",
        )

    if asset.status == AssetStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived asset cannot receive new versions."
        )

    if not can_update_asset(session, collection, asset, creator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create asset version.",
        )

    if (stored_object := await get_user_object(session, dto.object_id, creator.id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID {dto.object_id!r} not found.",
        )

    await _validate_asset_version_uniqueness(session, asset_id, stored_object.id)

    number = await get_next_asset_version_number(session, asset_id)
    version = AssetVersion(
        asset_id=asset.id,
        object_id=stored_object.id,
        number=number,
        original_filename=dto.original_filename,
    )
    session.add(version)
    await session.flush()

    return version


async def get_asset_versions(
    session: AsyncSession,
    asset_id: UUID,
    *,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[AssetVersion]:
    stmt = (
        select(AssetVersion)
        .where(AssetVersion.asset_id == asset_id)
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()

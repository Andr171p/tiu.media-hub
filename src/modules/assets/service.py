from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import AuthUser, PermissionDeniedError
from src.core.common.exceptions import InvalidDataError, NotFoundError
from src.modules.collections import (
    Action,
    CollectionAccess,
    UploadPolicy,
    get_access,
    validate_custom_meta,
)
from src.modules.media import StoredObject, get_owned_object
from src.modules.tags import AssetTag, Tag, set_asset_tags
from src.modules.users import sync_profile

from .meta import kind_of
from .models import Asset, AssetVersion
from .queries import select_assets
from .schemas import AssetFilters, CreateAssetDTO, UpdateAssetDTO


@dataclass(frozen=True, slots=True)
class AssetContext:
    """Актив вместе с правами пользователя в его коллекции."""

    asset: Asset
    access: CollectionAccess
    user: AuthUser

    @property
    def can_edit(self) -> bool:
        """Модераторы редактируют любые активы, участники — только свои."""

        return self.access.can(Action.MODERATE) or (
            self.access.can(Action.CONTRIBUTE) and self.asset.author_id == self.user.user.id
        )

    def require_edit(self) -> None:
        if not self.can_edit:
            raise PermissionDeniedError("Not allowed to edit this asset.")


def check_upload_policy(policy: UploadPolicy, obj: StoredObject) -> None:
    if not policy.allows(obj.content_type):
        raise InvalidDataError(
            "File type is not allowed in this collection.",
            details={"contentType": obj.content_type},
        )
    if obj.size_bytes > policy.max_file_size:
        raise InvalidDataError(
            "File is too large for this collection.", details={"maxFileSize": policy.max_file_size}
        )


async def get_context(session: AsyncSession, asset_id: UUID, user: AuthUser) -> AssetContext:
    if (asset := await session.scalar(select_assets().where(Asset.id == asset_id))) is None:
        raise NotFoundError("Asset not found.")

    access = await get_access(session, asset.collection_id, user)
    return AssetContext(asset, access, user)


async def get_asset(session: AsyncSession, asset_id: UUID) -> Asset:
    """Актив без проверки прав: для доверенных сервисов."""

    if (asset := await session.scalar(select_assets().where(Asset.id == asset_id))) is None:
        raise NotFoundError("Asset not found.")
    return asset


async def create_asset(
    session: AsyncSession,
    access: CollectionAccess,
    user: AuthUser,
    dto: CreateAssetDTO,
) -> tuple[Asset, AssetVersion]:
    """Создаёт актив с первой версией. Версия становится текущей, когда обработка подтвердит файл."""

    access.require(Action.CONTRIBUTE)
    settings = access.collection.settings

    obj = await get_owned_object(session, dto.object_id, user_id=user.user.id)
    check_upload_policy(settings.upload, obj)
    custom_meta = validate_custom_meta(settings.metadata_fields, dto.custom_meta)
    author = await sync_profile(session, user.user)

    asset = Asset(
        collection_id=access.collection.id,
        title=dto.title or PurePath(dto.original_filename).stem or dto.original_filename,
        description=dto.description,
        kind=kind_of(obj.content_type),
        author_id=author.id,
        custom_meta=custom_meta,
        license=dto.license,
    )
    session.add(asset)
    await session.flush()

    version = AssetVersion(
        asset_id=asset.id,
        number=1,
        object_id=obj.id,
        original_filename=dto.original_filename,
        created_by=author.id,
    )
    session.add(version)
    await session.flush()

    if dto.tags:
        await set_asset_tags(session, asset.id, dto.tags)

    return asset, version


async def list_assets(
    session: AsyncSession,
    access: CollectionAccess,
    filters: AssetFilters,
) -> tuple[list[Asset], int]:
    stmt = select_assets().where(Asset.collection_id == access.collection.id, Asset.status == filters.status)

    if filters.kind is not None:
        stmt = stmt.where(Asset.kind == filters.kind)
    if filters.query:
        stmt = stmt.where(Asset.title.ilike(f"%{filters.query.strip()}%"))
    if filters.tag:
        stmt = stmt.where(
            Asset.tags.any(AssetTag.tag.has(Tag.name == " ".join(filters.tag.split()).casefold())),
        )

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    assets = await session.scalars(
        stmt.order_by(Asset.created_at.desc(), Asset.id).limit(filters.limit).offset(filters.offset),
    )
    return list(assets), total


async def update_asset(session: AsyncSession, context: AssetContext, dto: UpdateAssetDTO) -> None:
    context.require_edit()
    asset = context.asset

    for field in dto.model_fields_set:
        value = getattr(dto, field)

        match field:
            case "title" if value is None:
                raise InvalidDataError("Title cannot be empty.")
            case "status" if value is None:
                raise InvalidDataError("Status cannot be empty.")
            case "custom_meta":
                value = validate_custom_meta(context.access.collection.settings.metadata_fields, value or {})

        setattr(asset, field, value)

    await session.flush()


async def set_tags(session: AsyncSession, context: AssetContext, names: list[str]) -> None:
    context.require_edit()
    await set_asset_tags(session, context.asset.id, names)
    # Изменение тегов — изменение актива: поднимаем updated_at
    context.asset.updated_at = datetime.now(UTC)
    await session.flush()


async def delete_asset(session: AsyncSession, context: AssetContext) -> None:
    context.require_edit()
    context.asset.deleted_at = datetime.now(UTC)
    await session.flush()


__all__ = [
    "AssetContext",
    "check_upload_policy",
    "create_asset",
    "delete_asset",
    "get_asset",
    "get_context",
    "list_assets",
    "set_tags",
    "update_asset",
]

"""Сборка ответов API из нескольких модулей: права, ожидающие версии, статистика коллекций, ссылки."""

from typing import Annotated

from collections.abc import Sequence
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import AuthUser
from src.core.cdn import CdnClient
from src.core.s3 import S3Client
from src.modules import assets, collections
from src.modules.assets import Asset, AssetContext, AssetResponse
from src.modules.collections import CollectionAccess, CollectionResponse, CollectionRole, ImageWatermark
from src.modules.media import StoredObject

_WATERMARK_URL_EXPIRES_IN = 10 * 60


class Presenter:
    def __init__(self, cdn: CdnClient, s3: S3Client) -> None:
        self._cdn = cdn
        self._s3 = s3

    async def assets(
        self,
        db: AsyncSession,
        items: Sequence[Asset],
        *,
        user: AuthUser | None,
    ) -> list[AssetResponse]:
        """Активы из любых коллекций. ``user=None`` — доверенный сервис, только чтение."""

        collection_ids = {asset.collection_id for asset in items}
        if user is not None:
            accesses = await collections.get_accesses(db, collection_ids, user)
        else:
            found = await collections.get_collections(db, collection_ids)
            accesses = {key: CollectionAccess(value, CollectionRole.VIEWER) for key, value in found.items()}

        pending = await assets.get_pending_versions(db, items)

        return [
            assets.to_asset_response(
                asset,
                cdn=self._cdn,
                settings=access.collection.settings,
                can_edit=user is not None and AssetContext(asset, access, user).can_edit,
                pending_version=pending.get(asset.id),
            )
            for asset in items
            if (access := accesses.get(asset.collection_id)) is not None
        ]

    async def asset(self, db: AsyncSession, context: AssetContext) -> AssetResponse:
        pending = await assets.get_pending_versions(db, [context.asset])
        return assets.to_asset_response(
            context.asset,
            cdn=self._cdn,
            settings=context.access.collection.settings,
            can_edit=context.can_edit,
            pending_version=pending.get(context.asset.id),
        )

    async def _watermark_urls(
        self, db: AsyncSession, accesses: Sequence[CollectionAccess]
    ) -> dict[UUID, str]:
        """Временные ссылки на изображения водяных знаков: для превью в редакторе знака."""

        object_ids = {
            access.collection.id: watermark.object_id
            for access in accesses
            if isinstance(watermark := access.collection.settings.watermark, ImageWatermark)
        }
        if not object_ids:
            return {}

        keys = dict(
            (
                await db.execute(
                    select(StoredObject.id, StoredObject.storage_key).where(
                        StoredObject.id.in_(object_ids.values())
                    ),
                )
            )
            .tuples()
            .all(),
        )
        return {
            collection_id: await self._s3.create_download_url(
                keys[object_id],
                filename="watermark",
                expires_in=_WATERMARK_URL_EXPIRES_IN,
            )
            for collection_id, object_id in object_ids.items()
            if object_id in keys
        }

    async def collections(
        self, db: AsyncSession, accesses: Sequence[CollectionAccess]
    ) -> list[CollectionResponse]:
        ids = [access.collection.id for access in accesses]
        stats = await assets.get_collection_stats(db, self._cdn, ids)
        watermarks = await self._watermark_urls(db, accesses)

        return [
            collections.to_collection_response(
                access,
                stats.get(access.collection.id),
                watermark_url=watermarks.get(access.collection.id),
            )
            for access in accesses
        ]

    async def collection(self, db: AsyncSession, access: CollectionAccess) -> CollectionResponse:
        [response] = await self.collections(db, [access])
        return response


def get_presenter(request: Request) -> Presenter:
    return Presenter(request.app.state.cdn, request.app.state.s3)


PresenterDep = Annotated[Presenter, Depends(get_presenter)]

__all__ = ["Presenter", "PresenterDep"]

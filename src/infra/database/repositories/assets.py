from typing import Any, Literal

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from ddf.application.dtos import CursorPagination, Page, Sort
from ddf.infra.database.sqlalchemy import SqlAlchemyRepository
from ddf.infra.database.sqlalchemy.utils import paginate
from sqlalchemy import ColumnElement, Date, and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.assets.repositories import (
    AssetFilter,
    AssetQueryRepository,
    AssetRepository,
    AssetVersionRepository,
    UploadRepository,
)
from src.domain.assets import (
    Asset,
    AssetKind,
    AssetVersion,
    License,
    LicenseStatus,
    Rendition,
    StoredFile,
    Upload,
    VersionMeta,
)
from src.domain.assets.license import EXPIRING_WITHIN

from ..codec import from_json, to_json
from ..models import AssetOrm, AssetVersionOrm, FaceOrm, UploadOrm


class AssetMapper:
    def to_model(self, entity: Asset) -> AssetOrm:
        return AssetOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            collection_id=entity.collection_id,
            title=entity.title,
            kind=entity.kind.value,
            created_by=entity.created_by,
            description=entity.description,
            caption=entity.caption,
            tags=list(entity.tags),
            metadata_=entity.metadata,
            license=to_json(License, entity.license) if entity.license else None,
            current_version_id=entity.current_version_id,
            version_count=entity.version_count,
        )

    def from_model(self, model: AssetOrm) -> Asset:
        return Asset(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            collection_id=model.collection_id,
            title=model.title,
            kind=AssetKind(model.kind),
            created_by=model.created_by,
            description=model.description,
            caption=model.caption,
            tags=tuple(model.tags),
            metadata=model.metadata_,
            license=from_json(License, model.license) if model.license else None,
            current_version_id=model.current_version_id,
            version_count=model.version_count,
        )


class AssetVersionMapper:
    def to_model(self, entity: AssetVersion) -> AssetVersionOrm:
        return AssetVersionOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            asset_id=entity.asset_id,
            number=entity.number,
            file_key=entity.file.key,
            file_name=entity.file.name,
            content_type=entity.file.content_type,
            size=entity.file.size,
            created_by=entity.created_by,
            source_version_id=entity.source_version_id,
            note=entity.note,
            sha256=entity.sha256,
            meta=to_json(VersionMeta, entity.meta) if entity.meta else None,
            renditions=to_json(tuple[Rendition, ...], entity.renditions),
            processed_at=entity.processed_at,
            processing_error=entity.processing_error,
        )

    def from_model(self, model: AssetVersionOrm) -> AssetVersion:
        return AssetVersion(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            asset_id=model.asset_id,
            number=model.number,
            file=StoredFile(
                key=model.file_key, name=model.file_name, content_type=model.content_type, size=model.size
            ),
            created_by=model.created_by,
            source_version_id=model.source_version_id,
            note=model.note,
            sha256=model.sha256,
            meta=from_json(VersionMeta, model.meta) if model.meta else None,
            renditions=from_json(tuple[Rendition, ...], model.renditions),
            processed_at=model.processed_at,
            processing_error=model.processing_error,
        )


class UploadMapper:
    def to_model(self, entity: Upload) -> UploadOrm:
        return UploadOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            collection_id=entity.collection_id,
            created_by=entity.created_by,
            file_key=entity.file.key,
            file_name=entity.file.name,
            content_type=entity.file.content_type,
            size=entity.file.size,
            asset_id=entity.asset_id,
            multipart_id=entity.multipart_id,
            expires_at=entity.expires_at,
        )

    def from_model(self, model: UploadOrm) -> Upload:
        return Upload(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            collection_id=model.collection_id,
            created_by=model.created_by,
            file=StoredFile(
                key=model.file_key, name=model.file_name, content_type=model.content_type, size=model.size
            ),
            asset_id=model.asset_id,
            multipart_id=model.multipart_id,
            expires_at=model.expires_at,
        )


class SqlAlchemyAssetRepository(SqlAlchemyRepository[Asset, AssetOrm], AssetRepository):
    model = AssetOrm
    data_mapper = AssetMapper()

    async def read(self, uid: UUID, with_lock: bool = False) -> Asset | None:
        stmt = select(AssetOrm).where(AssetOrm.id == uid)
        if with_lock:
            stmt = stmt.with_for_update()

        model = await self._session.scalar(stmt)
        return self.data_mapper.from_model(model) if model else None

    async def find_trashed_before(self, moment: datetime, *, limit: int) -> Sequence[Asset]:
        stmt = (
            select(AssetOrm)
            .where(AssetOrm.deleted_at.is_not(None), AssetOrm.deleted_at < moment)
            .order_by(AssetOrm.deleted_at)
            .limit(limit)
        )
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


class SqlAlchemyAssetVersionRepository(
    SqlAlchemyRepository[AssetVersion, AssetVersionOrm], AssetVersionRepository
):
    model = AssetVersionOrm
    data_mapper = AssetVersionMapper()

    async def list_by_asset(self, asset_id: UUID) -> Sequence[AssetVersion]:
        stmt = (
            select(AssetVersionOrm)
            .where(AssetVersionOrm.asset_id == asset_id)
            .order_by(AssetVersionOrm.number.desc())
        )
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


class SqlAlchemyUploadRepository(SqlAlchemyRepository[Upload, UploadOrm], UploadRepository):
    model = UploadOrm
    data_mapper = UploadMapper()

    async def find_expired(self, now: datetime, *, limit: int) -> Sequence[Upload]:
        stmt = (
            select(UploadOrm).where(UploadOrm.expires_at <= now).order_by(UploadOrm.expires_at).limit(limit)
        )
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


# =========================================================================================================
# Фильтрация списка активов
# =========================================================================================================

_LICENSE_START = AssetOrm.license["period"]["start"].astext.cast(Date)
_LICENSE_END = AssetOrm.license["period"]["end"].astext.cast(Date)


def _license_condition(status: LicenseStatus | Literal["none"], today: date) -> ColumnElement[bool]:
    """Повторяет ``License.status`` на SQL."""

    started = or_(_LICENSE_START.is_(None), today >= _LICENSE_START)
    expiring_from = today + EXPIRING_WITHIN

    match status:
        case "none":
            return AssetOrm.license.is_(None)
        case LicenseStatus.NOT_STARTED:
            return today < _LICENSE_START
        case LicenseStatus.EXPIRED:
            return and_(started, today > _LICENSE_END)
        case LicenseStatus.EXPIRING:
            return and_(started, today <= _LICENSE_END, expiring_from >= _LICENSE_END)
        case LicenseStatus.ACTIVE:
            return and_(
                AssetOrm.license.is_not(None),
                started,
                or_(_LICENSE_END.is_(None), expiring_from < _LICENSE_END),
            )

    raise ValueError(f"Unknown license status: {status!r}")


def build_conditions(asset_filter: AssetFilter) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        AssetOrm.deleted_at.is_not(None) if asset_filter.trashed else AssetOrm.deleted_at.is_(None)
    ]

    if asset_filter.collection_ids is not None:
        conditions.append(
            AssetOrm.collection_id.in_(asset_filter.collection_ids)
            if asset_filter.collection_ids
            else false()
        )
    if asset_filter.asset_ids is not None:
        conditions.append(AssetOrm.id.in_(asset_filter.asset_ids))
    if asset_filter.kinds:
        conditions.append(AssetOrm.kind.in_([kind.value for kind in asset_filter.kinds]))
    if asset_filter.tags:
        conditions.append(AssetOrm.tags.contains(list(asset_filter.tags)))
    if asset_filter.created_by is not None:
        conditions.append(AssetOrm.created_by == asset_filter.created_by)
    if asset_filter.person_id is not None:
        conditions.append(
            select(FaceOrm.id)
            .where(
                FaceOrm.asset_id == AssetOrm.id,
                FaceOrm.version_id == AssetOrm.current_version_id,
                FaceOrm.person_id == asset_filter.person_id,
            )
            .exists()
        )
    if asset_filter.license is not None:
        conditions.append(_license_condition(asset_filter.license, date.today()))
    if asset_filter.usable_on is not None:
        day = asset_filter.usable_on
        conditions.append(
            or_(
                AssetOrm.license.is_(None),
                and_(
                    or_(_LICENSE_START.is_(None), day >= _LICENSE_START),
                    or_(_LICENSE_END.is_(None), day <= _LICENSE_END),
                ),
            )
        )

    return conditions


class SqlAlchemyAssetQueryRepository(AssetQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._mapper = AssetMapper()

    async def find(
        self,
        asset_filter: AssetFilter,
        pagination: CursorPagination,
        *,
        sort: Literal["created_at", "updated_at"] = "created_at",
    ) -> Page[Asset]:
        stmt: Any = select(AssetOrm).where(*build_conditions(asset_filter))

        return await paginate(
            session=self._session,
            model=AssetOrm,
            stmt=stmt,
            pagination=pagination,
            from_model=self._mapper.from_model,
            sort=Sort(field=sort, direction="desc"),
        )


__all__ = [
    "SqlAlchemyAssetQueryRepository",
    "SqlAlchemyAssetRepository",
    "SqlAlchemyAssetVersionRepository",
    "SqlAlchemyUploadRepository",
    "build_conditions",
]

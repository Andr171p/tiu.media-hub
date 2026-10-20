from collections.abc import Sequence
from uuid import UUID

from ddf.infra.database.sqlalchemy import SqlAlchemyRepository
from sqlalchemy import and_, func, or_, select

from src.application.collections.repositories import (
    CollectionListItem,
    CollectionMemberRepository,
    CollectionRepository,
)
from src.domain.collections import (
    Collection,
    CollectionMember,
    CollectionRole,
    MetadataField,
    UploadPolicy,
    Visibility,
)

from ..codec import from_json, to_json
from ..models import AssetOrm, CollectionMemberOrm, CollectionOrm


class CollectionMapper:
    def to_model(self, entity: Collection) -> CollectionOrm:
        return CollectionOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            name=entity.name,
            description=entity.description,
            owner_id=entity.owner_id,
            visibility=entity.visibility.value,
            upload_policy=to_json(UploadPolicy, entity.upload_policy),
            metadata_schema=to_json(tuple[MetadataField, ...], entity.metadata_schema),
        )

    def from_model(self, model: CollectionOrm) -> Collection:
        return Collection(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            name=model.name,
            description=model.description,
            owner_id=model.owner_id,
            visibility=Visibility(model.visibility),
            upload_policy=from_json(UploadPolicy, model.upload_policy),
            metadata_schema=from_json(tuple[MetadataField, ...], model.metadata_schema),
        )


class CollectionMemberMapper:
    def to_model(self, entity: CollectionMember) -> CollectionMemberOrm:
        return CollectionMemberOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            collection_id=entity.collection_id,
            user_id=entity.user_id,
            role=entity.role.value,
        )

    def from_model(self, model: CollectionMemberOrm) -> CollectionMember:
        return CollectionMember(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            collection_id=model.collection_id,
            user_id=model.user_id,
            role=CollectionRole(model.role),
        )


def _readable_by(user_id: UUID):
    is_member = (
        select(CollectionMemberOrm.id)
        .where(CollectionMemberOrm.collection_id == CollectionOrm.id, CollectionMemberOrm.user_id == user_id)
        .exists()
    )
    return or_(
        CollectionOrm.owner_id == user_id,
        CollectionOrm.visibility == Visibility.INTERNAL.value,
        is_member,
    )


class SqlAlchemyCollectionRepository(SqlAlchemyRepository[Collection, CollectionOrm], CollectionRepository):
    model = CollectionOrm
    data_mapper = CollectionMapper()

    async def get_role(self, collection_id: UUID, user_id: UUID) -> CollectionRole | None:
        role = await self._session.scalar(
            select(CollectionMemberOrm.role).where(
                CollectionMemberOrm.collection_id == collection_id, CollectionMemberOrm.user_id == user_id
            )
        )
        return CollectionRole(role) if role else None

    async def list_visible(self, user_id: UUID | None) -> list[CollectionListItem]:
        asset_count = (
            select(func.count(AssetOrm.id))
            .where(AssetOrm.collection_id == CollectionOrm.id, AssetOrm.deleted_at.is_(None))
            .scalar_subquery()
        )
        role = select(CollectionMemberOrm.role).where(
            CollectionMemberOrm.collection_id == CollectionOrm.id, CollectionMemberOrm.user_id == user_id
        )
        stmt = select(CollectionOrm, role.scalar_subquery(), asset_count).order_by(CollectionOrm.name)

        if user_id is not None:
            stmt = stmt.where(_readable_by(user_id))

        rows = await self._session.execute(stmt)
        return [
            CollectionListItem(
                collection=self.data_mapper.from_model(model),
                role=CollectionRole(member_role) if member_role else None,
                asset_count=count,
            )
            for model, member_role, count in rows
        ]

    async def readable_ids(self, user_id: UUID) -> list[UUID]:
        return list(await self._session.scalars(select(CollectionOrm.id).where(_readable_by(user_id))))

    async def count_assets(self, collection_id: UUID) -> int:
        return (
            await self._session.scalar(
                select(func.count(AssetOrm.id)).where(AssetOrm.collection_id == collection_id)
            )
            or 0
        )


class SqlAlchemyCollectionMemberRepository(
    SqlAlchemyRepository[CollectionMember, CollectionMemberOrm], CollectionMemberRepository
):
    model = CollectionMemberOrm
    data_mapper = CollectionMemberMapper()

    async def get_member(self, collection_id: UUID, user_id: UUID) -> CollectionMember | None:
        model = await self._session.scalar(
            select(CollectionMemberOrm).where(
                and_(
                    CollectionMemberOrm.collection_id == collection_id, CollectionMemberOrm.user_id == user_id
                )
            )
        )
        return self.data_mapper.from_model(model) if model else None

    async def list_members(self, collection_id: UUID) -> Sequence[CollectionMember]:
        stmt = (
            select(CollectionMemberOrm)
            .where(CollectionMemberOrm.collection_id == collection_id)
            .order_by(CollectionMemberOrm.created_at)
        )
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]

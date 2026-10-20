"""Репозитории комментариев, подборок и порталов."""

from collections.abc import Sequence
from uuid import UUID

from ddf.infra.database.sqlalchemy import SqlAlchemyRepository
from sqlalchemy import or_, select

from src.application.comments import CommentRepository
from src.application.portals.ports import PortalRepository
from src.application.selections import SelectionRepository
from src.domain.comments import Anchor, Comment
from src.domain.portals import Block, Portal, PortalAccess, Theme
from src.domain.selections import Selection

from ..codec import from_json, to_json
from ..models import CommentOrm, PortalOrm, SelectionOrm


class CommentMapper:
    def to_model(self, entity: Comment) -> CommentOrm:
        return CommentOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            asset_id=entity.asset_id,
            version_id=entity.version_id,
            author_id=entity.author_id,
            text=entity.text,
            parent_id=entity.parent_id,
            anchor=to_json(Anchor, entity.anchor) if entity.anchor else None,
            resolved_at=entity.resolved_at,
            resolved_by=entity.resolved_by,
        )

    def from_model(self, model: CommentOrm) -> Comment:
        return Comment(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            asset_id=model.asset_id,
            version_id=model.version_id,
            author_id=model.author_id,
            text=model.text,
            parent_id=model.parent_id,
            anchor=from_json(Anchor, model.anchor) if model.anchor else None,
            resolved_at=model.resolved_at,
            resolved_by=model.resolved_by,
        )


class SelectionMapper:
    def to_model(self, entity: Selection) -> SelectionOrm:
        return SelectionOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            name=entity.name,
            description=entity.description,
            owner_id=entity.owner_id,
            shared=entity.shared,
            asset_ids=list(entity.asset_ids),
        )

    def from_model(self, model: SelectionOrm) -> Selection:
        return Selection(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            name=model.name,
            description=model.description,
            owner_id=model.owner_id,
            shared=model.shared,
            asset_ids=list(model.asset_ids),
        )


class PortalMapper:
    def to_model(self, entity: Portal) -> PortalOrm:
        return PortalOrm(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            slug=entity.slug,
            title=entity.title,
            description=entity.description,
            owner_id=entity.owner_id,
            theme=to_json(Theme, entity.theme),
            blocks=to_json(tuple[Block, ...], entity.blocks),
            access=entity.access.value,
            password_hash=entity.password_hash,
            allow_download=entity.allow_download,
            published_at=entity.published_at,
        )

    def from_model(self, model: PortalOrm) -> Portal:
        return Portal(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            slug=model.slug,
            title=model.title,
            description=model.description,
            owner_id=model.owner_id,
            theme=from_json(Theme, model.theme),
            blocks=from_json(tuple[Block, ...], model.blocks),
            access=PortalAccess(model.access),
            password_hash=model.password_hash,
            allow_download=model.allow_download,
            published_at=model.published_at,
        )


class SqlAlchemyCommentRepository(SqlAlchemyRepository[Comment, CommentOrm], CommentRepository):
    model = CommentOrm
    data_mapper = CommentMapper()

    async def list_by_asset(self, asset_id: UUID) -> Sequence[Comment]:
        stmt = select(CommentOrm).where(CommentOrm.asset_id == asset_id).order_by(CommentOrm.created_at)
        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


class SqlAlchemySelectionRepository(SqlAlchemyRepository[Selection, SelectionOrm], SelectionRepository):
    model = SelectionOrm
    data_mapper = SelectionMapper()

    async def list_visible(self, user_id: UUID | None) -> Sequence[Selection]:
        stmt = select(SelectionOrm).order_by(SelectionOrm.updated_at.desc())
        if user_id is not None:
            stmt = stmt.where(or_(SelectionOrm.owner_id == user_id, SelectionOrm.shared.is_(True)))

        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]


class SqlAlchemyPortalRepository(SqlAlchemyRepository[Portal, PortalOrm], PortalRepository):
    model = PortalOrm
    data_mapper = PortalMapper()

    async def find_by_slug(self, slug: str) -> Portal | None:
        model = await self._session.scalar(select(PortalOrm).where(PortalOrm.slug == slug))
        return self.data_mapper.from_model(model) if model else None

    async def list_owned(self, owner_id: UUID | None) -> Sequence[Portal]:
        stmt = select(PortalOrm).order_by(PortalOrm.updated_at.desc())
        if owner_id is not None:
            stmt = stmt.where(PortalOrm.owner_id == owner_id)

        return [self.data_mapper.from_model(model) for model in await self._session.scalars(stmt)]

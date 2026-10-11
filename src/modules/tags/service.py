from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.common.exceptions import ConflictError, InvalidDataError, NotFoundError

from .models import AssetTag, Tag, TagSource
from .schemas import CreateTagDTO, TagResponse, UpdateTagDTO

_MAX_TAG_LENGTH = 64


def normalize_tag(name: str) -> str:
    return " ".join(name.split()).casefold()[:_MAX_TAG_LENGTH]


def autotag_prompt(tag: Tag) -> str:
    return tag.prompt or tag.name


async def get_or_create_tags(session: AsyncSession, names: Iterable[str]) -> list[Tag]:
    normalized = list(dict.fromkeys(name for raw in names if (name := normalize_tag(raw))))
    if not normalized:
        return []

    await session.execute(
        insert(Tag)
        .values([{"name": name} for name in normalized])
        .on_conflict_do_nothing(index_elements=["name"]),
    )
    tags = {tag.name: tag for tag in await session.scalars(select(Tag).where(Tag.name.in_(normalized)))}
    return [tags[name] for name in normalized]


async def set_asset_tags(session: AsyncSession, asset_id: UUID, names: Iterable[str]) -> None:
    """
    Заменяет теги актива. Оставшиеся теги сохраняют источник: принятый автотег остаётся автотегом,
    а удалённый пользователем — удаляется.
    """

    tags = await get_or_create_tags(session, names)
    wanted = {tag.id for tag in tags}

    current = set((await session.scalars(select(AssetTag.tag_id).where(AssetTag.asset_id == asset_id))).all())

    if removed := current - wanted:
        await session.execute(
            delete(AssetTag).where(AssetTag.asset_id == asset_id, AssetTag.tag_id.in_(removed))
        )

    session.add_all(
        AssetTag(asset_id=asset_id, tag_id=tag_id, source=TagSource.MANUAL) for tag_id in wanted - current
    )
    await session.flush()


async def apply_auto_tags(
    session: AsyncSession, asset_id: UUID, scored: Sequence[tuple[UUID, float]]
) -> None:
    """Заменяет автотеги актива результатом классификации. Ручные теги не трогает."""

    scores = dict(scored)

    await session.execute(
        delete(AssetTag).where(
            AssetTag.asset_id == asset_id,
            AssetTag.source == TagSource.AUTO,
            AssetTag.tag_id.not_in(scores),
        ),
    )
    if scores:
        stmt = insert(AssetTag).values(
            [
                {
                    "asset_id": asset_id,
                    "tag_id": tag_id,
                    "source": TagSource.AUTO,
                    "confidence": score,
                }
                for tag_id, score in scores.items()
            ],
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["asset_id", "tag_id"],
                set_={"confidence": stmt.excluded.confidence},
                where=AssetTag.source == TagSource.AUTO,
            ),
        )
    await session.flush()


async def search_tags(session: AsyncSession, query: str, *, limit: int = 20) -> Sequence[Tag]:
    stmt = select(Tag).order_by(Tag.name).limit(limit)
    if prefix := normalize_tag(query):
        stmt = stmt.where(Tag.name.startswith(prefix, autoescape=True))
    return (await session.scalars(stmt)).all()


# =================================================================================================
# Словарь автотегирования (администрирование)
# =================================================================================================


async def list_tags(session: AsyncSession, *, auto_assign: bool | None = None) -> list[TagResponse]:
    usage = func.count(AssetTag.id).label("usage")
    stmt = (
        select(Tag, usage).outerjoin(AssetTag, AssetTag.tag_id == Tag.id).group_by(Tag.id).order_by(Tag.name)
    )
    if auto_assign is not None:
        stmt = stmt.where(Tag.auto_assign.is_(auto_assign))

    rows = await session.execute(stmt)
    return [
        TagResponse.model_validate(tag).model_copy(update={"usage_count": count})
        for tag, count in rows.tuples()
    ]


async def list_auto_tags(session: AsyncSession) -> Sequence[Tag]:
    return (await session.scalars(select(Tag).where(Tag.auto_assign.is_(True)))).all()


async def create_tag(session: AsyncSession, dto: CreateTagDTO) -> Tag:
    if not (name := normalize_tag(dto.name)):
        raise InvalidDataError("Tag name is empty.")

    if await session.scalar(select(Tag.id).where(Tag.name == name)) is not None:
        raise ConflictError("Tag already exists.")

    tag = Tag(name=name, auto_assign=dto.auto_assign, prompt=dto.prompt)
    session.add(tag)
    await session.flush()
    return tag


async def update_tag(session: AsyncSession, tag_id: UUID, dto: UpdateTagDTO) -> Tag:
    if (tag := await session.get(Tag, tag_id)) is None:
        raise NotFoundError("Tag not found.")

    for field, value in dto.model_dump(exclude_unset=True).items():
        setattr(tag, field, value)
    await session.flush()
    return tag


async def delete_tag(session: AsyncSession, tag_id: UUID) -> None:
    if (tag := await session.get(Tag, tag_id)) is None:
        raise NotFoundError("Tag not found.")
    await session.delete(tag)


__all__ = [
    "apply_auto_tags",
    "autotag_prompt",
    "create_tag",
    "delete_tag",
    "get_or_create_tags",
    "list_auto_tags",
    "list_tags",
    "normalize_tag",
    "search_tags",
    "set_asset_tags",
    "update_tag",
]

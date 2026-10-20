from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from ddf.application.repositories import Repository

from src.domain.collections import Collection, CollectionMember, CollectionRole


@dataclass(frozen=True, slots=True)
class CollectionListItem:
    collection: Collection
    role: CollectionRole | None
    asset_count: int


class CollectionRepository(Repository[Collection]):
    async def get_role(self, collection_id: UUID, user_id: UUID) -> CollectionRole | None:
        """Роль участника; ``None`` — не участник."""
        raise NotImplementedError

    async def list_visible(self, user_id: UUID | None) -> list[CollectionListItem]:
        """Коллекции, которые пользователь может читать; ``None`` — все (администратор)."""
        raise NotImplementedError

    async def readable_ids(self, user_id: UUID) -> list[UUID]:
        raise NotImplementedError

    async def count_assets(self, collection_id: UUID) -> int:
        """Все активы коллекции, включая корзину."""
        raise NotImplementedError


class CollectionMemberRepository(Repository[CollectionMember]):
    async def get_member(self, collection_id: UUID, user_id: UUID) -> CollectionMember | None:
        raise NotImplementedError

    async def list_members(self, collection_id: UUID) -> Sequence[CollectionMember]:
        raise NotImplementedError


__all__ = ["CollectionListItem", "CollectionMemberRepository", "CollectionRepository"]

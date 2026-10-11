"""
Права внутри коллекции. Модель как у репозиториев: владелец, модераторы, участники, публичный просмотр.

=========== ======== ========== =========== ==========
Действие     viewer   member     moderator   owner
=========== ======== ========== =========== ==========
VIEW         да       да         да          да
CONTRIBUTE   нет      да         да          да
MODERATE     нет      нет        да          да
MANAGE       нет      нет        нет         да
=========== ======== ========== =========== ==========

Администратор DAM (роль ``admin`` клиента API) действует как владелец любой коллекции.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from src.core.auth import AuthUser, PermissionDeniedError

from .models import Collection, MemberRole, Visibility


class CollectionRole(IntEnum):
    """Эффективная роль: упорядочена, старшая роль включает права младших."""

    VIEWER = 1
    MEMBER = 2
    MODERATOR = 3
    OWNER = 4

    @property
    def label(self) -> str:
        return self.name.lower()


class Action(StrEnum):
    VIEW = "view"
    CONTRIBUTE = "contribute"
    """Загружать активы и редактировать свои."""

    MODERATE = "moderate"
    """Редактировать любые активы, управлять участниками, настройками и водяным знаком."""

    MANAGE = "manage"
    """Видимость, модераторы, удаление коллекции."""


_REQUIRED_ROLE = {
    Action.VIEW: CollectionRole.VIEWER,
    Action.CONTRIBUTE: CollectionRole.MEMBER,
    Action.MODERATE: CollectionRole.MODERATOR,
    Action.MANAGE: CollectionRole.OWNER,
}

_MEMBER_ROLES = {
    MemberRole.MEMBER: CollectionRole.MEMBER,
    MemberRole.MODERATOR: CollectionRole.MODERATOR,
}


def resolve_role(
    collection: Collection,
    user: AuthUser,
    member_role: MemberRole | None,
) -> CollectionRole | None:
    if user.is_admin or collection.owner_id == user.user.id:
        return CollectionRole.OWNER

    if member_role is not None:
        return _MEMBER_ROLES[member_role]

    if collection.visibility is Visibility.PUBLIC:
        return CollectionRole.VIEWER

    return None


@dataclass(frozen=True, slots=True)
class CollectionAccess:
    """Коллекция вместе с правами текущего пользователя в ней."""

    collection: Collection
    role: CollectionRole

    def can(self, action: Action) -> bool:
        return self.role >= _REQUIRED_ROLE[action]

    def require(self, action: Action) -> None:
        if not self.can(action):
            raise PermissionDeniedError(f"Action {action.value!r} is not allowed in this collection.")

    @property
    def permissions(self) -> list[Action]:
        return [action for action in Action if self.can(action)]


__all__ = ["Action", "CollectionAccess", "CollectionRole", "resolve_role"]

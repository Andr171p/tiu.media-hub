from typing import Literal

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ddf.domain.exceptions import InvariantViolationError
from ddf.domain.models import AggregateRoot


class PortalAccess(StrEnum):
    PUBLIC = "public"
    """Любой, у кого есть ссылка."""

    PASSWORD = "password"
    EMPLOYEES = "employees"
    """Только вошедшие сотрудники."""


@dataclass(frozen=True, kw_only=True)
class Theme:
    accent_color: str = "#2563EB"
    logo_asset_id: UUID | None = None
    cover_asset_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class HeroBlock:
    type: Literal["hero"] = "hero"
    title: str
    subtitle: str | None = None
    image_asset_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class TextBlock:
    type: Literal["text"] = "text"
    markdown: str


@dataclass(frozen=True, kw_only=True)
class GalleryBlock:
    """Живая галерея: показывает актуальное содержимое коллекции или подборки."""

    type: Literal["gallery"] = "gallery"
    title: str | None = None
    collection_id: UUID | None = None
    selection_id: UUID | None = None
    tags: tuple[str, ...] = ()
    """Только активы со всеми этими тегами."""

    limit: int = 60

    def __post_init__(self) -> None:
        if (self.collection_id is None) == (self.selection_id is None):
            raise InvariantViolationError("Gallery needs exactly one source: a collection or a selection.")


@dataclass(frozen=True, kw_only=True)
class FilesBlock:
    """Список файлов для скачивания: пресс-релизы, логотипы."""

    type: Literal["files"] = "files"
    title: str | None = None
    asset_ids: tuple[UUID, ...]


type Block = HeroBlock | TextBlock | GalleryBlock | FilesBlock


@dataclass(frozen=True, slots=True)
class PortalSources:
    collection_ids: frozenset[UUID]
    selection_ids: frozenset[UUID]
    asset_ids: frozenset[UUID]


@dataclass(kw_only=True)
class Portal(AggregateRoot):
    """Брендированный мини-сайт из блоков. Содержимое всегда актуально: блоки ссылаются на источники."""

    slug: str
    title: str
    description: str | None = None
    owner_id: UUID
    theme: Theme = field(default_factory=Theme)
    blocks: tuple[Block, ...] = ()
    access: PortalAccess = PortalAccess.PUBLIC
    password_hash: str | None = None
    allow_download: bool = False
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        self.set_access(self.access, self.password_hash)

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    def set_access(self, access: PortalAccess, password_hash: str | None = None) -> None:
        """Пароль обязателен для доступа по паролю; новый хеш можно не передавать, если он уже задан."""

        if access is not PortalAccess.PASSWORD:
            self.access, self.password_hash = access, None
            return

        if (password_hash or self.password_hash) is None:
            raise InvariantViolationError("Password access requires a password.")

        self.access = access
        self.password_hash = password_hash or self.password_hash

    def sources(self) -> PortalSources:
        """Коллекции, подборки и активы, на которые ссылается портал."""

        asset_ids = {
            asset_id for asset_id in (self.theme.logo_asset_id, self.theme.cover_asset_id) if asset_id
        }
        collection_ids: set[UUID] = set()
        selection_ids: set[UUID] = set()

        for block in self.blocks:
            match block:
                case HeroBlock(image_asset_id=UUID() as asset_id):
                    asset_ids.add(asset_id)
                case GalleryBlock(collection_id=UUID() as collection_id):
                    collection_ids.add(collection_id)
                case GalleryBlock(selection_id=UUID() as selection_id):
                    selection_ids.add(selection_id)
                case FilesBlock():
                    asset_ids.update(block.asset_ids)

        return PortalSources(
            collection_ids=frozenset(collection_ids),
            selection_ids=frozenset(selection_ids),
            asset_ids=frozenset(asset_ids),
        )

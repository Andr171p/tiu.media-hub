from typing import Annotated, Literal

from datetime import datetime
from uuid import UUID

from pydantic import Field, StringConstraints

from src.application.dtos import CamelModel
from src.domain.assets import AssetKind
from src.domain.portals import (
    Block,
    FilesBlock,
    GalleryBlock,
    HeroBlock,
    PortalAccess,
    TextBlock,
    Theme,
)

type Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
type Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)]


class ThemeDTO(CamelModel):
    accent_color: str = Field(default="#2563EB", pattern=r"^#[0-9a-fA-F]{6}$")
    logo_asset_id: UUID | None = None
    cover_asset_id: UUID | None = None

    def to_domain(self) -> Theme:
        return Theme(
            accent_color=self.accent_color,
            logo_asset_id=self.logo_asset_id,
            cover_asset_id=self.cover_asset_id,
        )


class HeroBlockDTO(CamelModel):
    type: Literal["hero"] = "hero"
    title: Title
    subtitle: str | None = Field(default=None, max_length=1000)
    image_asset_id: UUID | None = None

    def to_domain(self) -> HeroBlock:
        return HeroBlock(title=self.title, subtitle=self.subtitle, image_asset_id=self.image_asset_id)


class TextBlockDTO(CamelModel):
    type: Literal["text"] = "text"
    markdown: str = Field(min_length=1, max_length=20000)

    def to_domain(self) -> TextBlock:
        return TextBlock(markdown=self.markdown)


class GalleryBlockDTO(CamelModel):
    """Источник — коллекция или подборка (ровно один)."""

    type: Literal["gallery"] = "gallery"
    title: str | None = Field(default=None, max_length=255)
    collection_id: UUID | None = None
    selection_id: UUID | None = None
    tags: list[str] = Field(default_factory=list, description="Только активы со всеми этими тегами")
    limit: int = Field(default=60, ge=1, le=200)

    def to_domain(self) -> GalleryBlock:
        return GalleryBlock(
            title=self.title,
            collection_id=self.collection_id,
            selection_id=self.selection_id,
            tags=tuple(self.tags),
            limit=self.limit,
        )


class FilesBlockDTO(CamelModel):
    type: Literal["files"] = "files"
    title: str | None = Field(default=None, max_length=255)
    asset_ids: list[UUID] = Field(min_length=1, max_length=100)

    def to_domain(self) -> FilesBlock:
        return FilesBlock(title=self.title, asset_ids=tuple(self.asset_ids))


type BlockDTO = Annotated[
    HeroBlockDTO | TextBlockDTO | GalleryBlockDTO | FilesBlockDTO, Field(discriminator="type")
]


def block_to_dto(block: Block) -> BlockDTO:
    match block:
        case HeroBlock():
            return HeroBlockDTO(
                title=block.title, subtitle=block.subtitle, image_asset_id=block.image_asset_id
            )
        case TextBlock():
            return TextBlockDTO(markdown=block.markdown)
        case GalleryBlock():
            return GalleryBlockDTO(
                title=block.title,
                collection_id=block.collection_id,
                selection_id=block.selection_id,
                tags=list(block.tags),
                limit=block.limit,
            )
        case FilesBlock():
            return FilesBlockDTO(title=block.title, asset_ids=list(block.asset_ids))


class CreatePortalDTO(CamelModel):
    slug: Slug = Field(description="Адрес портала", examples=["press"])
    title: Title
    description: str | None = Field(default=None, max_length=2000)
    theme: ThemeDTO = Field(default_factory=ThemeDTO)
    blocks: list[BlockDTO] = Field(default_factory=list, max_length=50)
    access: PortalAccess = PortalAccess.PUBLIC
    password: str | None = Field(
        default=None, min_length=6, max_length=128, description="Для доступа по паролю"
    )
    allow_download: bool = Field(default=False, description="Разрешить скачивание оригиналов")
    published: bool = False


class UpdatePortalDTO(CamelModel):
    slug: Slug | None = None
    title: Title | None = None
    description: str | None = Field(default=None, max_length=2000)
    theme: ThemeDTO | None = None
    blocks: list[BlockDTO] | None = Field(default=None, max_length=50)
    access: PortalAccess | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    allow_download: bool | None = None
    published: bool | None = None


class PortalResponse(CamelModel):
    id: UUID
    slug: str
    title: str
    description: str | None
    theme: ThemeDTO
    blocks: list[BlockDTO]
    access: PortalAccess
    allow_download: bool
    published_at: datetime | None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


# =========================================================================================================
# Публичное представление
# =========================================================================================================


class PublicAsset(CamelModel):
    id: UUID
    title: str
    description: str | None
    kind: AssetKind
    width: int | None
    height: int | None
    duration: float | None
    thumbnail_url: str | None
    preview_url: str | None
    video_url: str | None
    audio_url: str | None
    file_name: str
    file_size: int


class PublicHero(CamelModel):
    type: Literal["hero"] = "hero"
    title: str
    subtitle: str | None
    image: PublicAsset | None


class PublicText(CamelModel):
    type: Literal["text"] = "text"
    markdown: str


class PublicGallery(CamelModel):
    type: Literal["gallery"] = "gallery"
    title: str | None
    items: list[PublicAsset]


class PublicFiles(CamelModel):
    type: Literal["files"] = "files"
    title: str | None
    items: list[PublicAsset]


type PublicBlock = Annotated[
    PublicHero | PublicText | PublicGallery | PublicFiles, Field(discriminator="type")
]


class PublicPortal(CamelModel):
    slug: str
    title: str
    description: str | None
    accent_color: str
    logo: PublicAsset | None
    cover: PublicAsset | None
    blocks: list[PublicBlock]
    allow_download: bool


class UnlockPortalDTO(CamelModel):
    password: str = Field(min_length=1, max_length=128)


class PortalToken(CamelModel):
    token: str = Field(description="Передавайте в заголовке X-Portal-Token")
    expires_in: int

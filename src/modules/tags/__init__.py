from .models import AssetTag, Tag, TagSource
from .schemas import CreateTagDTO, TagResponse, UpdateTagDTO
from .service import (
    apply_auto_tags,
    autotag_prompt,
    create_tag,
    delete_tag,
    get_or_create_tags,
    list_auto_tags,
    list_tags,
    normalize_tag,
    search_tags,
    set_asset_tags,
    update_tag,
)

__all__ = [
    "AssetTag",
    "CreateTagDTO",
    "Tag",
    "TagResponse",
    "TagSource",
    "UpdateTagDTO",
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

from typing import NotRequired, TypedDict

from uuid import UUID


class AssetProcessingContext(TypedDict):
    """Контекст workflow для обработки медиа актива."""

    asset_id: UUID
    user_id: NotRequired[UUID]

    filename: str
    mime_type: str
    size: int

    storage_key: str

from typing import Any, NotRequired, TypedDict

from uuid import UUID

from src.core.assets.enums import AssetType


class AssetProcessingContext(TypedDict):
    """Контекст workflow для обработки медиа актива."""

    asset_id: UUID
    user_id: NotRequired[UUID]

    filename: str
    mime_type: str
    size: int

    storage_key: str


class UploadInspectionResult(TypedDict):
    """Результат проверки и идентификации загруженного файла."""

    asset_type: AssetType
    mime_type: str
    size: int
    checksum: str

    meta: NotRequired[dict[str, Any]]

from uuid import UUID

from .models import AssetType

DOCUMENT_PREFIXES: tuple[str, ...] = (
    "text/",
    "application/pdf",
    "application/rtf",
    "application/msword",
    "application/vnd.ms-",
    "application/vnd.openxmlformats-officedocument.",
)

MIME_TO_ASSET_TYPE_MAP: tuple[tuple[str, ...], AssetType] = (
    (("image/",), AssetType.IMAGE),
    (("video/",), AssetType.VIDEO),
    (("audio/",), AssetType.AUDIO),
    (DOCUMENT_PREFIXES, AssetType.DOCUMENT),
)


def resolve_asset_type(mime_type: str) -> AssetType:
    """Определяет тип актива по MIME-типу."""

    if not mime_type.strip():
        return AssetType.OTHER

    cleaned = mime_type.split(";", 1)[0].strip().lower()

    return next(
        (
            asset_type
            for prefixes, asset_type in MIME_TO_ASSET_TYPE_MAP
            if cleaned.startswith(prefixes)
        ),
        AssetType.OTHER,
    )


def build_original_storage_key(asset_id: UUID, version_id: UUID) -> str:
    """Формирует неизменяемый ключ хранилища для исходного ресурса."""

    return f"assets/{asset_id}/versions/{version_id}/original"

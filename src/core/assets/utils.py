from uuid import UUID

from .meta import AssetType

_DOCUMENT_PREFIXES: tuple[str, ...] = (
    "text/",
    "application/pdf",
    "application/rtf",
    "application/msword",
    "application/vnd.ms-",
    "application/vnd.openxmlformats-officedocument.",
)

_MIME_TO_ASSET_TYPE_MAP: tuple[tuple[str, ...], AssetType] = (
    (("image/",), AssetType.IMAGE),
    (("video/",), AssetType.VIDEO),
    (("audio/",), AssetType.AUDIO),
    (_DOCUMENT_PREFIXES, AssetType.DOCUMENT),
)


def resolve_asset_type(mime_type: str) -> AssetType:
    """Определяет тип актива по MIME-типу."""

    if not mime_type.strip():
        return AssetType.OTHER

    cleaned = mime_type.split(";", 1)[0].strip().lower()

    return next(
        (
            asset_type
            for prefixes, asset_type in _MIME_TO_ASSET_TYPE_MAP
            if cleaned.startswith(prefixes)
        ),
        AssetType.OTHER,
    )


def normalize_mime(mime_type: str) -> str:
    """Приводит Mime к единому формату, например: `text/plain; charset=utf-8` -> `text/plain`."""

    return mime_type.split(";", maxsplit=1)[0].strip().lower()


def is_mime_compatible(declared: str, detected: str) -> bool:
    """Проверяет совместимость заявленного и фактического Mime."""

    if declared == "application/octet-stream":
        return True

    if declared == detected:
        return True

    declared_family = declared.partition("/")[0]
    detected_family = detected.partition("/")[0]

    return (
        declared_family == detected_family
        and declared_family in {"image", "video", "audio", "text"}
    )


def build_storage_key(asset_id: UUID, source_id: UUID) -> str:
    return f"/assets/{asset_id}/sources/{source_id}"

from typing import Literal

import json
from collections.abc import Callable
from functools import partial
from uuid import NAMESPACE_OID, UUID, uuid5

from .enums import AssetType, DerivativeType

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


def generate_upload_id(asset_id: UUID, filename: str, mime_type: str, size: int) -> UUID:
    """Клюя для дудупликации потока загрузки."""

    payload = {
        "asset_id": asset_id.hex,
        "filename": filename,
        "mime_type": mime_type,
        "size": size,
    }
    serialized = json.dumps(payload, sort_keys=True)

    return uuid5(NAMESPACE_OID, serialized)


def _build_storage_key(
        type_: Literal["upload", "original", "derivative"],
        *,
        asset_id: UUID,
        upload_id: UUID | None = None,
        filename: str | None = None,
        version_id: UUID | None = None,
        derivative_type: DerivativeType | None = None,
) -> str:
    """Базовая функция для формирования ключа медиа объекта."""

    base_path = f"assets/{asset_id}"

    match type_:
        case "upload":
            if not upload_id or not filename:
                raise ValueError("The 'upload' requires an `upload_id` and `filename`.")

            return f"{base_path}/uploads/{upload_id}/{filename}"

        case "original":
            if not version_id:
                raise ValueError("The 'original' requires `version_id`.")

            return f"{base_path}/versions/{version_id}/original"

        case "derivative":
            if not version_id or not derivative_type:
                raise ValueError("The 'derivative' required `version_id` and `derivative_type`.")

            return f"{base_path}/versions/{version_id}/derivatives/{derivative_type.value}"

        case _:
            raise ValueError(f"Unsupported key type: {type_!r}.")


build_upload_storage_key = partial(_build_storage_key, "upload")
build_original_storage_key = partial(_build_storage_key, "original")
build_derivative_storage_key = partial(_build_storage_key, "derivative")

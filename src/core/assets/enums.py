from enum import StrEnum


class AssetType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class AssetStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

    ARCHIVED = "archived"
    DELETED = "deleted"


class DerivativeType(StrEnum):
    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"
    WATERMARKED = "watermarked"

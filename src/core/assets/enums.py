from enum import StrEnum


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
    POSTER = "poster"
    WAVEFORM = "waveform"
    CONVERTED = "converted"
    TRANSCRIPT = "transcript"

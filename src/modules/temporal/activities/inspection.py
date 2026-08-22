from typing import NamedTuple

import asyncio
import hashlib

import magic
from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.core.assets.helpers import is_mime_compatible, normalize_mime, resolve_asset_type
from src.core.temporal.dtos import AssetProcessingContext, UploadInspectionResult
from src.modules.s3 import s3_client

_MAGIC_SAMPLE_SIZE = 8 * 1024
_STREAM_CHUNK_SIZE = 8 * 1024 * 1024
_HEARTBEAT_BYTES = 32 * 1024 * 1024


class StreamResult(NamedTuple):
    """Результат сквозного чтения файла из S3."""

    sha256_hex: str
    sample_bytes: bytes
    processed_bytes: int


async def _process_file_stream(storage_key: str) -> StreamResult:

    hasher = hashlib.sha256()
    sample = bytearray()

    processed_bytes = 0
    next_heartbeat = _HEARTBEAT_BYTES

    async for chunk in s3_client.download_stream(storage_key, chunk_size=_STREAM_CHUNK_SIZE):

        hasher.update(chunk)
        processed_bytes += len(chunk)

        if len(sample) < _MAGIC_SAMPLE_SIZE:
            remaining = _MAGIC_SAMPLE_SIZE - len(sample)
            sample.extend(chunk[:remaining])

        if processed_bytes >= next_heartbeat:
            activity.heartbeat({"processed_bytes": processed_bytes})
            next_heartbeat += _HEARTBEAT_BYTES

    return StreamResult(
        sha256_hex=hasher.hexdigest(),
        sample_bytes=bytes(sample),
        processed_bytes=processed_bytes,
    )


async def _detect_mime_type(sample: bytes) -> str:
    """Определяет Mime тип файла по первым байтам."""

    if not sample:
        raise ValueError("Uploaded file is empty.")

    detected = await asyncio.to_thread(magic.from_buffer, sample, mime=True)
    return normalize_mime(detected)


@activity.defn(name="inspect_upload")
async def inspect_upload(context: AssetProcessingContext) -> UploadInspectionResult:
    """Проверяет загруженный медиа файл."""

    storage_key = context["storage_key"]
    metadata = await s3_client.get_metadata(storage_key)

    expected_size = context["size"]
    uploaded_size = metadata.get("Content-Length", 0)

    if uploaded_size != expected_size:
        raise ApplicationError(
            "Uploaded file size does not match expected size. "
            f"Actual size: {uploaded_size}, expected size: {expected_size}.",
            non_retryable=True,
        )

    result = await _process_file_stream(storage_key)

    if result.processed_bytes != expected_size:
        raise ApplicationError(
            "Uploaded file size changed during inspection. "
            f"Processed bytes: {result.processed_bytes}, expected size: {expected_size}.",
            non_retryable=True,
        )

    declared_mime = normalize_mime(context["mime_type"])
    detected_mime = await _detect_mime_type(result.sample_bytes)

    if not is_mime_compatible(declared_mime, detected_mime):
        raise ApplicationError(
            f"Declared MIME type does not match detected MIME type: "
            f"{declared_mime!r} != {detected_mime!r}.",
            non_retryable=True,
        )

    asset_type = resolve_asset_type(detected_mime)

    return UploadInspectionResult(
        asset_type=asset_type,
        mime_type=detected_mime,
        size=uploaded_size,
        checksum=result.sha256_hex,
    )

from typing import Any, BinaryIO, Protocol

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from aiobotocore.client import AioBaseClient
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from .config import S3Config

# Минимальный размер чанка для загрузки в S3
_MIN_CHUNK_SIZE = 5 * 1024 * 1024


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class S3Client:
    def __init__(self, config: S3Config) -> None:
        self._config = config
        self.session = get_session()

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[AioBaseClient]:
        async with self.session.create_client(**self._config.model_dump()) as client:
            yield client

    async def upload(self, file: BinaryIO, storage_key: str, mime_type: str) -> None:
        async with self.get_client() as client:
            await client.put_object(
                Bucket=self._config.bucket,
                Body=file,
                Key=storage_key,
                ContentType=mime_type,
            )

    async def delete(self, storage_key: str) -> None:
        async with self.get_client() as client:
            await client.delete_object(Bucket=self._config.bucket, Key=storage_key)

    async def create_upload_url(
            self, storage_key: str, mime_type: str, expires_in: int = 3600
    ) -> str:
        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._config.bucket,
                    "Key": storage_key,
                    "ContentType": mime_type,
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )

    async def create_download_url(self, storage_key: str, expires_in: int = 3600) -> str:
        async with self.get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": storage_key},
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )

    async def get_metadata(self, storage_key: str) -> dict[str, Any]:
        try:
            async with self.get_client() as client:
                return await client.head_object(Bucket=self._config.bucket, Key=storage_key)
        except ClientError:
            raise NotFoundError(f"File not found by key - {storage_key}") from None

    async def upload_stream(
            self,
            file_stream: AsyncReadable,
            storage_key: str,
            mime_type: str,
            chunk_size: int = _MIN_CHUNK_SIZE,
    ) -> None:
        """Потоковая загрузка через Multipart upload."""

        if chunk_size < _MIN_CHUNK_SIZE:
            raise ValueError("chunk_size must be at least 5 MiB for S3 multipart upload.")

        async with self.get_client as client:

            response = await client.create_multipart_upload(
                Bucket=self._config.bucket,
                Key=storage_key,
                ContentType=mime_type,
            )

            upload_id = response["UploadId"]
            parts: list[dict[str, Any]] = []

            try:  # noqa: PLW0717, RUF105
                part_number = 1

                while chunk := await file_stream.read(chunk_size):
                    part = await client.upload_part(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                    )

                    parts.append({"ETag": part["ETag"], "PartNumber": part_number})
                    part_number += 1

                if not parts:
                    await client.abort_multipart_upload(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        UploadId=upload_id,
                    )

                    await client.put_object(
                        Bucket=self._config.bucket,
                        Key=storage_key,
                        ContentType=mime_type,
                        Body=b"",
                    )
                    return

                await client.complete_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )

            except Exception:
                await client.abort_multipart_upload(
                    Bucket=self._config.bucket,
                    Key=storage_key,
                    UploadId=upload_id,
                )
                raise

    async def download_stream(
            self, storage_key: str, chunk_size: int = _MIN_CHUNK_SIZE,
    ) -> AsyncIterator[bytes]:
        """Потоковое чтение объекта из S3."""

        stack = AsyncExitStack()

        try:
            client = await stack.enter_async_context(self.get_client())
            response = await client.get_object(Bucket=self._config.bucket, Key=storage_key)

            body = response["Body"]

            try:
                while chunk := await body.read(chunk_size):
                    yield chunk
            finally:
                body.close()
        finally:
            await stack.aclose()

from typing import BinaryIO

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from aiobotocore.client import AioBaseClient
from aiobotocore.config import AioConfig
from botocore.exceptions import ClientError
from ddf.infra.s3 import S3Client, S3Config

from src.application.storage import FileStorage, UploadedPart

from .config import StorageConfig

_SMALL_FILE = 64 * 1024 * 1024
_PART_SIZE = 64 * 1024 * 1024
_DELETE_BATCH = 1000


class _S3Client(S3Client):
    """Клиент DDF с подписью SigV4: presigned URL по умолчанию подписываются устаревшей SigV2."""

    def __init__(self, config: S3Config) -> None:
        super().__init__(config)
        self._settings = config

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[AioBaseClient]:
        config = AioConfig(signature_version="s3v4", s3={"addressing_style": self._settings.addressing_style})
        async with self.session.create_client(
            service_name=self._settings.service_name,
            endpoint_url=str(self._settings.endpoint_url),
            region_name=self._settings.region,
            aws_access_key_id=self._settings.access_key,
            aws_secret_access_key=self._settings.secret_key.get_secret_value(),
            config=config,
        ) as client:
            yield client


class _ThreadedReader:
    """Асинхронное чтение локального файла для multipart-загрузки DDF."""

    def __init__(self, file: BinaryIO) -> None:
        self._file = file

    async def read(self, size: int = -1) -> bytes:
        return await asyncio.to_thread(self._file.read, size)


class S3FileStorage(FileStorage):
    """
    Бакет хранилища. Внутренние операции идут на ``endpoint_url``,
    presigned URL подписываются публичным адресом: браузер ходит в хранилище через nginx.
    """

    def __init__(self, config: StorageConfig, bucket: str) -> None:
        self._bucket = bucket
        common = {
            "access_key": config.access_key,
            "secret_key": config.secret_key,
            "region": config.region,
            "bucket": bucket,
        }
        self._client = _S3Client(S3Config(endpoint_url=config.endpoint_url, **common))
        self._public = _S3Client(S3Config(endpoint_url=config.public_endpoint_url, **common))

    async def create_upload_url(self, key: str, content_type: str, *, expires_in: int) -> str:
        return await self._public.create_upload_url(key, content_type, expires_in=expires_in)

    async def start_multipart_upload(self, key: str, content_type: str) -> str:
        async with self._client.get_client() as client:
            response = await client.create_multipart_upload(
                Bucket=self._bucket, Key=key, ContentType=content_type
            )
            return response["UploadId"]

    async def create_part_upload_urls(
        self, key: str, multipart_id: str, *, parts: int, expires_in: int
    ) -> list[str]:
        async with self._public.get_client() as client:
            return [
                await client.generate_presigned_url(
                    "upload_part",
                    Params={
                        "Bucket": self._bucket,
                        "Key": key,
                        "UploadId": multipart_id,
                        "PartNumber": number,
                    },
                    ExpiresIn=expires_in,
                    HttpMethod="PUT",
                )
                for number in range(1, parts + 1)
            ]

    async def complete_multipart_upload(
        self, key: str, multipart_id: str, parts: Sequence[UploadedPart]
    ) -> None:
        async with self._client.get_client() as client:
            await client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=multipart_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": part.number, "ETag": part.etag}
                        for part in sorted(parts, key=lambda part: part.number)
                    ]
                },
            )

    async def abort_multipart_upload(self, key: str, multipart_id: str) -> None:
        async with self._client.get_client() as client:
            await client.abort_multipart_upload(Bucket=self._bucket, Key=key, UploadId=multipart_id)

    async def get_size(self, key: str) -> int | None:
        try:
            async with self._client.get_client() as client:
                response = await client.head_object(Bucket=self._bucket, Key=key)
        except ClientError:
            return None

        return response["ContentLength"]

    async def create_download_url(self, key: str, *, filename: str, expires_in: int) -> str:
        async with self._public.get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                },
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )

    async def download_file(self, key: str, path: Path) -> None:
        with path.open("wb") as file:
            async for chunk in self._client.download_stream(key):
                await asyncio.to_thread(file.write, chunk)

    async def download_bytes(self, key: str) -> bytes:
        async with self._client.get_client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as body:
                return await body.read()

    async def upload_file(self, key: str, path: Path, content_type: str) -> None:
        if (await asyncio.to_thread(path.stat)).st_size <= _SMALL_FILE:
            await self.upload_bytes(key, await asyncio.to_thread(path.read_bytes), content_type)
            return

        with path.open("rb") as file:
            await self._client.upload_stream(_ThreadedReader(file), key, content_type, chunk_size=_PART_SIZE)

    async def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        await self._client.upload(data, key, content_type)

    async def delete_many(self, keys: Sequence[str]) -> None:
        async with self._client.get_client() as client:
            for start in range(0, len(keys), _DELETE_BATCH):
                batch = keys[start : start + _DELETE_BATCH]
                await client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True}
                )


__all__ = ["S3FileStorage"]

from typing import Any, BinaryIO

from contextlib import asynccontextmanager

from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from .config import S3Config


class S3Client:
    def __init__(self, config: S3Config) -> None:
        self._config = config
        self.session = get_session()

    @asynccontextmanager
    async def get_client(self):
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

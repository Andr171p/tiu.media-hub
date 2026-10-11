import base64
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from dataclasses import dataclass
from urllib.parse import quote

from aiobotocore.client import AioBaseClient
from aiobotocore.config import AioConfig
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from .config import S3Config
from .exceptions import S3NotFoundError

_NOT_FOUND_CODES = frozenset({"404", "NoSuchKey", "NotFound"})
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_DELETE_BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    size: int
    content_type: str | None
    sha256: str | None
    """SHA-256 в hex, если объект загружен с контрольной суммой."""


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    headers: dict[str, str]
    """Заголовки, которые клиент обязан отправить: они входят в подпись."""


def _hex_to_base64(sha256_hex: str) -> str:
    return base64.b64encode(bytes.fromhex(sha256_hex)).decode()


def _base64_to_hex(value: str) -> str:
    return base64.b64decode(value).hex()


def _content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _is_not_found(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES


class S3Client:
    """
    Долгоживущий клиент S3. Соединение открывается в ``connect`` и закрывается в ``close``.

    Presigned URL подписываются отдельным клиентом с публичным адресом: подпись SigV4 включает
    host, поэтому URL должен быть подписан тем адресом, по которому к S3 обратится браузер.
    Подпись вычисляется локально, сетевых запросов этот клиент не делает.
    """

    def __init__(self, config: S3Config) -> None:
        self._config = config
        self._stack = AsyncExitStack()
        self._client: AioBaseClient | None = None
        self._signer: AioBaseClient | None = None

    @property
    def bucket(self) -> str:
        return self._config.bucket

    async def connect(self) -> None:
        session = get_session()
        options = {
            "region_name": self._config.region,
            "aws_access_key_id": self._config.access_key,
            "aws_secret_access_key": self._config.secret_key.get_secret_value(),
            # Контрольные суммы задаём сами (SHA-256): CRC, который SDK добавляет по умолчанию, не нужен
            "config": AioConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        }
        self._client = await self._stack.enter_async_context(
            session.create_client("s3", endpoint_url=self._config.endpoint_url, **options),
        )
        self._signer = await self._stack.enter_async_context(
            session.create_client(
                "s3",
                endpoint_url=self._config.public_endpoint_url or self._config.endpoint_url,
                **options,
            ),
        )

    async def close(self) -> None:
        await self._stack.aclose()
        self._client = self._signer = None

    @property
    def _s3(self) -> AioBaseClient:
        if self._client is None:
            raise RuntimeError("S3 client is not connected.")
        return self._client

    @property
    def _presigner(self) -> AioBaseClient:
        if self._signer is None:
            raise RuntimeError("S3 client is not connected.")
        return self._signer

    async def create_upload_url(
        self,
        key: str,
        *,
        content_type: str,
        sha256: str,
        expires_in: int,
    ) -> PresignedUpload:
        """
        URL для прямой загрузки. Контрольная сумма входит в подпись: хранилище само отклонит файл,
        содержимое которого не совпадает с заявленным SHA-256.
        """

        checksum = _hex_to_base64(sha256)
        url = await self._presigner.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "ChecksumSHA256": checksum,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
        headers = {"Content-Type": content_type, "x-amz-checksum-sha256": checksum}
        return PresignedUpload(url=url, headers=headers)

    async def create_download_url(self, key: str, *, filename: str, expires_in: int) -> str:
        return await self._presigner.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": _content_disposition(filename),
            },
            ExpiresIn=expires_in,
            HttpMethod="GET",
        )

    async def get_info(self, key: str) -> ObjectInfo:
        try:
            response = await self._s3.head_object(Bucket=self.bucket, Key=key, ChecksumMode="ENABLED")
        except ClientError as exc:
            if _is_not_found(exc):
                raise S3NotFoundError(f"Object {key!r} not found.") from None
            raise

        checksum = response.get("ChecksumSHA256")
        return ObjectInfo(
            size=response["ContentLength"],
            content_type=response.get("ContentType"),
            # Для multipart-загрузок S3 возвращает «сумму сумм» с суффиксом -N: это не SHA-256 файла
            sha256=_base64_to_hex(checksum) if checksum and "-" not in checksum else None,
        )

    async def iter_chunks(self, key: str, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
        """Потоковое чтение объекта."""

        try:
            response = await self._s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if _is_not_found(exc):
                raise S3NotFoundError(f"Object {key!r} not found.") from None
            raise

        async with response["Body"] as body:
            while chunk := await body.read(chunk_size):
                yield chunk

    async def read(self, key: str) -> bytes:
        return b"".join([chunk async for chunk in self.iter_chunks(key)])

    async def put_immutable(self, key: str, body: bytes, *, content_type: str) -> None:
        """Сохраняет объект, который по этому ключу никогда не меняется (производные версий)."""

        await self._s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl=_IMMUTABLE_CACHE_CONTROL,
        )

    async def delete(self, *keys: str) -> None:
        for start in range(0, len(keys), _DELETE_BATCH_SIZE):
            batch = keys[start : start + _DELETE_BATCH_SIZE]
            await self._s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
            )


__all__ = ["ObjectInfo", "PresignedUpload", "S3Client"]

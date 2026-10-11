"""
Обработка версии актива:

1. захват — короткая транзакция: проверка статуса, учёт попыток, снимок нужных данных;
2. анализ — без открытой транзакции: SHA-256 содержимого, фактический MIME, политика коллекции,
   метаданные, производные (миниатюра и превью с водяным знаком параллельно);
3. запись результата — версия становится готовой и, если она последняя, текущей.

Каждый шаг идемпотентен: повторный запуск или параллельный воркер не испортят результат.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from tempfile import SpooledTemporaryFile
from uuid import UUID

from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.core.s3 import S3Client, S3NotFoundError
from src.modules.assets import (
    Asset,
    AssetVersion,
    Issue,
    IssueCode,
    IssueSeverity,
    Rendition,
    RenditionKind,
    VersionMeta,
    VersionStatus,
    kind_of,
)
from src.modules.collections import (
    Collection,
    ImageWatermark,
    TextWatermark,
    UploadPolicy,
    watermark_fingerprint,
)
from src.modules.media import Digest, StoredObject, describe_mismatch, stream_object, verify_object

from .config import ProcessingConfig
from .detection import SAMPLE_SIZE, detect_mime, effective_mime, is_compatible
from .extraction import UnprocessableFileError, extract
from .imaging import EncodedImage, open_image, prepare, render_preview, render_thumbnail

logger = logging.getLogger(__name__)

type Watermark = ImageWatermark | TextWatermark


@dataclass(frozen=True, slots=True)
class _Job:
    version_id: UUID
    asset_id: UUID
    object_id: UUID
    storage_key: str
    sha256: str
    size_bytes: int
    declared_type: str
    upload_policy: UploadPolicy
    watermark: Watermark | None
    watermark_key: str | None


@dataclass(frozen=True, slots=True)
class _RenditionFile:
    kind: RenditionKind
    key: str
    image: EncodedImage


@dataclass(slots=True)
class _Outcome:
    error: str | None = None
    integrity_error: str | None = None
    meta: VersionMeta | None = None
    issues: list[Issue] = field(default_factory=list)
    text: str | None = None
    renditions: list[_RenditionFile] = field(default_factory=list)


def _rendition_key(job: _Job, kind: RenditionKind, variant: str) -> str:
    return f"renditions/{job.asset_id}/{job.version_id}/{kind.value}-{variant}.webp"


class VersionProcessor:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        s3: S3Client,
        config: ProcessingConfig,
    ) -> None:
        self._sessions = sessions
        self._s3 = s3
        self._config = config

    # =============================================================================================
    # Обработка версии
    # =============================================================================================

    async def process(self, version_id: UUID) -> UUID | None:
        """Обрабатывает версию. Возвращает актив, если его текущая версия изменилась и нужна индексация."""

        if (job := await self._claim(version_id)) is None:
            return None

        outcome = await self._analyze(job)
        return await self._persist(job, outcome)

    async def _load_job(self, session: AsyncSession, version: AssetVersion) -> _Job:
        asset = await session.get_one(Asset, version.asset_id)
        collection = await session.get_one(Collection, asset.collection_id)
        watermark = collection.settings.watermark

        watermark_key = None
        if isinstance(watermark, ImageWatermark):
            mark = await session.get(StoredObject, watermark.object_id)
            watermark_key = mark.storage_key if mark else None

        return _Job(
            version_id=version.id,
            asset_id=asset.id,
            object_id=version.object.id,
            storage_key=version.object.storage_key,
            sha256=version.object.sha256,
            size_bytes=version.object.size_bytes,
            declared_type=version.object.content_type,
            upload_policy=collection.settings.upload,
            watermark=watermark,
            watermark_key=watermark_key,
        )

    async def _claim(self, version_id: UUID) -> _Job | None:
        async with self._sessions() as session, session.begin():
            version = await session.scalar(
                select(AssetVersion)
                .where(AssetVersion.id == version_id)
                .options(selectinload(AssetVersion.object))
                .with_for_update(of=AssetVersion),
            )
            if version is None or version.status is not VersionStatus.PROCESSING:
                return None

            version.attempts += 1
            if version.attempts > self._config.max_attempts:
                version.status = VersionStatus.FAILED
                version.error = "Не удалось обработать файл: превышено число попыток."
                version.processed_at = datetime.now(UTC)
                return None

            return await self._load_job(session, version)

    async def _analyze(self, job: _Job) -> _Outcome:
        with SpooledTemporaryFile(max_size=self._config.spool_max_size) as file:
            try:
                digest = await stream_object(self._s3, job.storage_key, sink=file)
            except S3NotFoundError:
                return _Outcome(
                    error="Оригинал отсутствует в хранилище.",
                    integrity_error="Object is missing in storage.",
                )

            if mismatch := describe_mismatch(Digest(sha256=job.sha256, size=job.size_bytes), digest):
                return _Outcome(
                    error="Нарушена целостность: файл в хранилище изменён.",
                    integrity_error=mismatch,
                )

            file.seek(0)
            detected = await asyncio.to_thread(detect_mime, file.read(SAMPLE_SIZE))
            mime_type = effective_mime(job.declared_type, detected)

            if not job.upload_policy.allows(mime_type):
                return _Outcome(error=f"Тип файла {mime_type} не разрешён в коллекции.")

            issues = []
            if not is_compatible(job.declared_type, detected):
                issues.append(
                    Issue(
                        code=IssueCode.CONTENT_TYPE_MISMATCH,
                        severity=IssueSeverity.WARNING,
                        message="Заявленный тип файла не совпадает с содержимым.",
                        details={"declared": job.declared_type, "detected": detected},
                    ),
                )

            file.seek(0)
            try:
                extracted = await asyncio.to_thread(extract, file, mime_type, self._config)
            except UnprocessableFileError as exc:
                return _Outcome(error=str(exc))

        renditions = await self._render(job, extracted.image) if extracted.image is not None else []
        return _Outcome(meta=extracted.meta, issues=issues, text=extracted.text, renditions=renditions)

    async def _load_mark(self, job: _Job) -> Image.Image | None:
        if job.watermark_key is None:
            return None
        try:
            return await asyncio.to_thread(open_image, await self._s3.read(job.watermark_key))
        except S3NotFoundError, OSError:
            logger.warning("Watermark image %s is unavailable", job.watermark_key, exc_info=True)
            return None

    async def _render_preview(self, job: _Job, image: Image.Image) -> _RenditionFile:
        preview = await asyncio.to_thread(
            render_preview,
            image,
            size=self._config.preview_size,
            quality=self._config.webp_quality,
            watermark=job.watermark,
            mark=await self._load_mark(job),
            font_path=self._config.watermark_font_path,
        )
        key = _rendition_key(job, RenditionKind.PREVIEW, watermark_fingerprint(job.watermark))
        return _RenditionFile(RenditionKind.PREVIEW, key, preview)

    async def _render(self, job: _Job, image: Image.Image) -> list[_RenditionFile]:
        base = await asyncio.to_thread(prepare, image)

        thumbnail, preview = await asyncio.gather(
            asyncio.to_thread(
                render_thumbnail,
                base,
                size=self._config.thumbnail_size,
                quality=self._config.webp_quality,
            ),
            self._render_preview(job, base),
        )
        files = [
            _RenditionFile(
                RenditionKind.THUMBNAIL,
                _rendition_key(job, RenditionKind.THUMBNAIL, "plain"),
                thumbnail,
            ),
            preview,
        ]

        await asyncio.gather(
            *(
                self._s3.put_immutable(item.key, item.image.data, content_type=item.image.content_type)
                for item in files
            ),
        )
        return files

    @staticmethod
    def _rendition(version_id: UUID, item: _RenditionFile) -> Rendition:
        return Rendition(
            version_id=version_id,
            kind=item.kind,
            storage_key=item.key,
            content_type=item.image.content_type,
            size_bytes=len(item.image.data),
            width=item.image.width,
            height=item.image.height,
        )

    async def _persist(self, job: _Job, outcome: _Outcome) -> UUID | None:
        async with self._sessions() as session, session.begin():
            version = await session.scalar(
                select(AssetVersion).where(AssetVersion.id == job.version_id).with_for_update(),
            )
            if version is None or version.status is not VersionStatus.PROCESSING:
                return None

            version.processed_at = datetime.now(UTC)

            if outcome.error is not None:
                version.status = VersionStatus.FAILED
                version.error = outcome.error
                if outcome.integrity_error is not None:
                    obj = await session.get_one(StoredObject, job.object_id)
                    obj.integrity_error = outcome.integrity_error
                return None

            version.status = VersionStatus.READY
            version.error = None
            version.meta = outcome.meta
            version.issues = outcome.issues
            version.extracted_text = outcome.text

            await session.execute(delete(Rendition).where(Rendition.version_id == version.id))
            session.add_all(self._rendition(version.id, item) for item in outcome.renditions)

            latest = await session.scalar(
                select(func.max(AssetVersion.number)).where(AssetVersion.asset_id == job.asset_id)
            )
            if version.number != latest:
                return None

            asset = await session.get_one(Asset, job.asset_id, with_for_update=True)
            asset.current_version_id = version.id
            if outcome.meta is not None:
                asset.kind = kind_of(outcome.meta.mime_type)
            return asset.id

    # =============================================================================================
    # Перерисовка превью при смене водяного знака
    # =============================================================================================

    async def rerender_preview(self, version_id: UUID) -> None:
        async with self._sessions() as session:
            version = await session.scalar(
                select(AssetVersion)
                .where(AssetVersion.id == version_id, AssetVersion.status == VersionStatus.READY)
                .options(selectinload(AssetVersion.object), selectinload(AssetVersion.renditions)),
            )
            if version is None or version.meta is None:
                return
            job = await self._load_job(session, version)
            mime_type = version.meta.mime_type
            current = next((item for item in version.renditions if item.kind is RenditionKind.PREVIEW), None)

        if current is None or current.storage_key == _rendition_key(
            job, RenditionKind.PREVIEW, watermark_fingerprint(job.watermark)
        ):
            return

        with SpooledTemporaryFile(max_size=self._config.spool_max_size) as file:
            await stream_object(self._s3, job.storage_key, sink=file)
            file.seek(0)
            extracted = await asyncio.to_thread(extract, file, mime_type, self._config)

        if extracted.image is None:
            return

        preview = await self._render_preview(job, await asyncio.to_thread(prepare, extracted.image))
        await self._s3.put_immutable(preview.key, preview.image.data, content_type=preview.image.content_type)

        async with self._sessions() as session, session.begin():
            rendition = await session.get(Rendition, current.id, with_for_update=True)
            if rendition is None:
                return
            rendition.storage_key = preview.key
            rendition.size_bytes = len(preview.image.data)
            rendition.width, rendition.height = preview.image.width, preview.image.height

        await self._s3.delete(current.storage_key)

    async def collection_versions(self, collection_id: UUID) -> Sequence[UUID]:
        """Готовые версии коллекции с превью: им нужно перерисовать водяной знак."""

        async with self._sessions() as session:
            stmt = (
                select(AssetVersion.id)
                .join(Asset, Asset.id == AssetVersion.asset_id)
                .join(Rendition, Rendition.version_id == AssetVersion.id)
                .where(
                    Asset.collection_id == collection_id,
                    Asset.deleted_at.is_(None),
                    AssetVersion.status == VersionStatus.READY,
                    Rendition.kind == RenditionKind.PREVIEW,
                )
            )
            return (await session.scalars(stmt)).all()

    # =============================================================================================
    # Обслуживание
    # =============================================================================================

    async def stale_versions(self) -> Sequence[UUID]:
        """Версии, обработка которых потерялась (воркер упал, сообщение не дошло)."""

        deadline = datetime.now(UTC) - timedelta(seconds=self._config.stale_after)
        async with self._sessions() as session:
            stmt = (
                select(AssetVersion.id)
                .where(
                    AssetVersion.status == VersionStatus.PROCESSING,
                    AssetVersion.updated_at < deadline,
                )
                .limit(500)
            )
            return (await session.scalars(stmt)).all()

    async def verify_integrity(self, object_id: UUID) -> bool | None:
        """Сверяет содержимое объекта в хранилище с SHA-256, подтверждённым при загрузке."""

        async with self._sessions() as session, session.begin():
            if (obj := await session.get(StoredObject, object_id)) is None:
                return None
            ok = await verify_object(self._s3, obj)
            if not ok:
                logger.error("Integrity check failed for object %s: %s", obj.id, obj.integrity_error)
            return ok

    async def object_ids(self) -> Sequence[UUID]:
        async with self._sessions() as session:
            return (await session.scalars(select(StoredObject.id))).all()


__all__ = ["VersionProcessor"]

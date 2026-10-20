"""
Обработка версии в фоне. Задачи идемпотентны: повторный запуск (at-least-once) не портит результат.

Транзакция не держится открытой во время долгой работы с файлом: после чтения соединение возвращается в пул.
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork

from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser, PermissionDeniedError
from src.application.outbox import save_events_to_outbox
from src.application.storage import FileStorage
from src.domain.assets import AssetKind, AssetVersion, Rendition, RenditionKind, StoredFile
from src.domain.assets import logic as assets

from .ports import Frame, ImageAnnotator, MediaProcessor, Transcriber, UnsupportedMediaError
from .repositories import TranscriptRepository

logger = logging.getLogger(__name__)

MAX_VIDEO_FRAMES = 24
ANNOTATION_FRAMES = 4

_EXTENSIONS = {"image/webp": ".webp", "image/jpeg": ".jpg", "video/mp4": ".mp4", "audio/mp4": ".m4a"}


def rendition_key(version_id: UUID, kind: RenditionKind, content_type: str) -> str:
    """Ключ производной. Варианты (например, с водяным знаком) получат суффикс к ``kind``."""

    return f"{version_id}/{kind}{_EXTENSIONS.get(content_type, '')}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


async def process_version(
    version_id: UUID,
    *,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    renditions: FileStorage,
    processor: MediaProcessor,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    """Метаданные и производные версии; по готовности — событие для поиска и ИИ."""

    version = await version_repository.read(version_id)
    await uow.rollback()  # освобождаем соединение на время работы с файлом

    if version is None or version.processed_at is not None:
        return

    with TemporaryDirectory(prefix="dam-") as tmp:
        workdir = Path(tmp)
        source = workdir / "source"
        await originals.download_file(version.file.key, source)
        sha256 = await asyncio.to_thread(_sha256, source)

        try:
            processed = await processor.process(source, version.kind, workdir)
        except UnsupportedMediaError as exc:
            logger.warning("Version %s cannot be processed: %s", version.id, exc)
            version.fail_processing(str(exc))
            await version_repository.update(version)
            await uow.commit()
            return

        stored: list[Rendition] = []
        for item in processed.renditions:
            key = rendition_key(version.id, item.kind, item.content_type)
            await renditions.upload_file(key, item.path, item.content_type)
            stored.append(
                Rendition(
                    kind=item.kind,
                    file=StoredFile(
                        key=key,
                        name=item.path.name,
                        content_type=item.content_type,
                        size=item.path.stat().st_size,
                    ),
                    width=item.width,
                    height=item.height,
                )
            )

    version.complete_processing(sha256=sha256, meta=processed.meta, renditions=tuple(stored))
    await version_repository.update(version)
    await save_events_to_outbox(outbox, version)
    await uow.commit()


async def load_frames(
    version: AssetVersion,
    *,
    renditions: FileStorage,
    processor: MediaProcessor,
    max_frames: int = MAX_VIDEO_FRAMES,
) -> list[Frame]:
    """Кадры для анализа: превью изображения/документа или выборка кадров прокси-видео."""

    if version.kind is AssetKind.VIDEO and (proxy := version.rendition(RenditionKind.VIDEO)):
        with TemporaryDirectory(prefix="dam-") as tmp:
            path = Path(tmp) / "proxy.mp4"
            await renditions.download_file(proxy.file.key, path)
            return await processor.sample_frames(path, max_frames=max_frames)

    if preview := version.rendition(RenditionKind.PREVIEW):
        return [Frame(image=await renditions.download_bytes(preview.file.key))]

    return []


async def annotate_version(
    version_id: UUID,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    renditions: FileStorage,
    processor: MediaProcessor,
    annotator: ImageAnnotator,
    uow: UnitOfWork,
) -> None:
    """ИИ-описание и теги. Теги добавляются к существующим, ручные правки не теряются."""

    version = await version_repository.read(version_id)
    await uow.rollback()

    if version is None or version.kind not in {AssetKind.IMAGE, AssetKind.VIDEO}:
        return

    frames = await load_frames(
        version, renditions=renditions, processor=processor, max_frames=ANNOTATION_FRAMES
    )
    if not frames:
        return

    annotation = await annotator.annotate(frames, kind=version.kind)

    asset = await asset_repository.read(version.asset_id, with_lock=True)
    if asset is None or asset.current_version_id != version.id:
        return

    asset.caption = annotation.caption
    asset.tags = assets.normalize_tags([*asset.tags, *annotation.tags])
    await asset_repository.update(asset)
    await uow.commit()


async def transcribe_version(
    version_id: UUID,
    *,
    version_repository: AssetVersionRepository,
    transcript_repository: TranscriptRepository,
    renditions: FileStorage,
    transcriber: Transcriber,
    uow: UnitOfWork,
) -> None:
    """Расшифровка речи: поиск по сказанному и переход к моменту в плеере."""

    version = await version_repository.read(version_id)
    await uow.rollback()

    if version is None:
        return

    proxy = version.rendition(RenditionKind.AUDIO) or version.rendition(RenditionKind.VIDEO)
    if proxy is None:
        return

    with TemporaryDirectory(prefix="dam-") as tmp:
        path = Path(tmp) / proxy.file.name
        await renditions.download_file(proxy.file.key, path)
        transcript = await transcriber.transcribe(path)

    await transcript_repository.save(version.id, transcript)
    await uow.commit()


async def reprocess_version(
    version_id: UUID,
    auth: AuthUser,
    *,
    version_repository: AssetVersionRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    """Администратор: обработать версию заново, затем заново проанализировать для поиска."""

    if not auth.is_admin:
        raise PermissionDeniedError("Administrator role required.")

    if (version := await version_repository.read(version_id)) is None:
        raise NotFoundError(f"Version with ID {version_id} not found.")

    version.restart_processing()
    await version_repository.update(version)
    await save_events_to_outbox(outbox, version)
    await uow.commit()


__all__ = [
    "annotate_version",
    "load_frames",
    "process_version",
    "rendition_key",
    "reprocess_version",
    "transcribe_version",
]

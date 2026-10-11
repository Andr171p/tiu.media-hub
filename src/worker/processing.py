"""
Задачи обработки файлов. Запуск воркера (процессы × асинхронные задачи в каждом):

    taskiq worker src.worker.processing:broker --workers 2 --max-async-tasks 4
"""

from typing import Annotated

import logging
from uuid import UUID

from taskiq import TaskiqDepends, TaskiqEvents, TaskiqState

from src.modules.media import expire_stale_uploads

from .brokers import indexing_broker, processing_broker
from .indexing import index_asset
from .resources import Resources, close_resources, create_resources, get_resources

logger = logging.getLogger(__name__)

broker = processing_broker

WorkerResources = Annotated[Resources, TaskiqDepends(get_resources)]


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.resources = await create_resources()
    # Обработка ставит задачи индексации: нужен клиент второго брокера
    await indexing_broker.startup()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await indexing_broker.shutdown()
    await close_resources(state.resources)


@broker.task(task_name="processing.process_version", retry_on_error=True)
async def process_version(version_id: str, resources: WorkerResources) -> None:
    if (asset_id := await resources.processor.process(UUID(version_id))) is not None:
        await index_asset.kiq(str(asset_id), with_image=True)


@broker.task(task_name="processing.rerender_preview", retry_on_error=True)
async def rerender_preview(version_id: str, resources: WorkerResources) -> None:
    await resources.processor.rerender_preview(UUID(version_id))


@broker.task(task_name="processing.rerender_collection_previews")
async def rerender_collection_previews(collection_id: str, resources: WorkerResources) -> None:
    """Водяной знак коллекции изменился: превью перерисовываются параллельно, по задаче на версию."""

    for version_id in await resources.processor.collection_versions(UUID(collection_id)):
        await rerender_preview.kiq(str(version_id))


@broker.task(task_name="processing.verify_integrity", retry_on_error=True)
async def verify_integrity(object_id: str, resources: WorkerResources) -> None:
    await resources.processor.verify_integrity(UUID(object_id))


@broker.task(task_name="processing.verify_all")
async def verify_all(resources: WorkerResources) -> None:
    for object_id in await resources.processor.object_ids():
        await verify_integrity.kiq(str(object_id))


@broker.task(task_name="processing.maintenance", schedule=[{"cron": "*/5 * * * *"}])
async def maintenance(resources: WorkerResources) -> None:
    """Самовосстановление: перезапуск потерянной обработки и уборка незавершённых загрузок."""

    stale = await resources.processor.stale_versions()
    for version_id in stale:
        await process_version.kiq(str(version_id))

    async with resources.sessions() as session, session.begin():
        expired = await expire_stale_uploads(session, resources.s3)

    if stale or expired:
        logger.info("Maintenance: requeued %d versions, expired %d uploads", len(stale), expired)


__all__ = [
    "broker",
    "maintenance",
    "process_version",
    "rerender_collection_previews",
    "rerender_preview",
    "verify_all",
    "verify_integrity",
]

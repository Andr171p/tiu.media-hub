"""
Задачи очереди ``media``. Запуск: ``taskiq worker src.infra.broker.media_tasks:media_broker``.
"""

import logging
from uuid import UUID

from taskiq import TaskiqDepends, TaskiqEvents, TaskiqState

from src.application.assets.uploads import cleanup_expired_uploads
from src.application.assets.usecases import purge_expired_trash
from src.application.editing import EditJob, EditQueue, render_edit
from src.application.processing.usecases import process_version
from src.infra.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyAssetVersionRepository,
    SqlAlchemyCollectionRepository,
    SqlAlchemyUploadRepository,
)
from src.infra.media.editor import EditorConfig, PillowImageEditor

from .brokers import media_broker
from .resources import WorkerResources, create_worker_resources

logger = logging.getLogger(__name__)


@media_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    logging.basicConfig(level=logging.INFO)
    state.resources = create_worker_resources()
    state.editor = PillowImageEditor(EditorConfig())


@media_broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await state.resources.close()


@media_broker.task(task_name="media.process_version", retry_on_error=True)
async def process_version_task(version_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources

    async with resources.session() as session:
        await process_version(
            UUID(version_id),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            originals=resources.originals,
            renditions=resources.renditions,
            processor=resources.processor,
            outbox=resources.outbox(session),
            uow=session,
        )


@media_broker.task(task_name="media.render_edit", retry_on_error=True)
async def render_edit_task(job: dict, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources

    async with resources.session() as session:
        await render_edit(
            EditJob.model_validate(job),
            asset_repository=SqlAlchemyAssetRepository(session),
            collection_repository=SqlAlchemyCollectionRepository(session),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            originals=resources.originals,
            editor=state.editor,
            outbox=resources.outbox(session),
            uow=session,
        )


@media_broker.task(task_name="media.cleanup", schedule=[{"cron": "*/30 * * * *"}])
async def cleanup_task(state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    """Брошенные загрузки и активы, пролежавшие в корзине 30 дней."""

    resources: WorkerResources = state.resources

    async with resources.session() as session:
        uploads = await cleanup_expired_uploads(
            upload_repository=SqlAlchemyUploadRepository(session), originals=resources.originals, uow=session
        )
        purged = await purge_expired_trash(
            asset_repository=SqlAlchemyAssetRepository(session),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            originals=resources.originals,
            renditions=resources.renditions,
            outbox=resources.outbox(session),
            uow=session,
        )

    logger.info("Cleanup: %d expired uploads, %d purged assets", uploads, purged)


class TaskiqEditQueue(EditQueue):
    async def enqueue(self, job: EditJob) -> None:
        await render_edit_task.kiq(job.model_dump(mode="json"))


__all__ = ["TaskiqEditQueue", "cleanup_task", "media_broker", "process_version_task", "render_edit_task"]

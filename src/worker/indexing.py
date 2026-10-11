"""
Задачи индексации поиска. Запуск воркера:

    taskiq worker src.worker.indexing:broker --workers 1 --max-async-tasks 16
"""

from typing import Annotated

from uuid import UUID

from taskiq import TaskiqDepends, TaskiqEvents, TaskiqState

from .brokers import indexing_broker
from .resources import Resources, close_resources, create_resources, get_resources

broker = indexing_broker

WorkerResources = Annotated[Resources, TaskiqDepends(get_resources)]


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.resources = await create_resources()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await close_resources(state.resources)


@broker.task(task_name="indexing.index_asset", retry_on_error=True)
async def index_asset(asset_id: str, resources: WorkerResources, with_image: bool = False) -> None:
    await resources.indexer.index_asset(UUID(asset_id), with_image=with_image)


@broker.task(task_name="indexing.remove_collection", retry_on_error=True)
async def remove_collection(collection_id: str, resources: WorkerResources) -> None:
    await resources.indexer.remove_collection(UUID(collection_id))


@broker.task(task_name="indexing.sync_tag_vocabulary", retry_on_error=True)
async def sync_tag_vocabulary(resources: WorkerResources) -> None:
    await resources.indexer.sync_tag_vocabulary()


@broker.task(task_name="indexing.reindex_all")
async def reindex_all(resources: WorkerResources) -> None:
    """Полная переиндексация: после смены модели эмбеддингов или поколения индекса."""

    await resources.indexer.sync_tag_vocabulary()
    for asset_id in await resources.indexer.asset_ids():
        await index_asset.kiq(str(asset_id), with_image=True)


__all__ = ["broker", "index_asset", "reindex_all", "remove_collection", "sync_tag_vocabulary"]

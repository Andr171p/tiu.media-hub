"""
Outbox relay: доставляет доменные события из ``outbox_messages`` в очереди задач (at-least-once).
Задачи идемпотентны, поэтому повторная доставка безопасна.

Запуск: ``python -m src.infra.outbox.relay``. Несколько экземпляров безопасны (``FOR UPDATE SKIP LOCKED``).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from ddf.application.outbox import OutboxConfig, OutboxProcessor
from ddf.domain.events import Event
from ddf.infra.database.sqlalchemy import PostgresConfig
from ddf.infra.outbox.sqlalchemy import (
    PostgresOutboxListener,
    SqlAlchemyOutboxStore,
    run_postgres_notify_worker,
)
from ddf.infra.outbox.worker import OutboxWorkerConfig
from dotenv import load_dotenv

from src.domain.assets import (
    AssetCurrentVersionChanged,
    AssetMoved,
    AssetPurged,
    AssetRestored,
    AssetTrashed,
    AssetVersionAdded,
    AssetVersionProcessed,
)
from src.domain.people import FaceAssigned
from src.infra.broker.ai_tasks import (
    ai_broker,
    annotate_task,
    detect_faces_task,
    index_visuals_task,
    propagate_face_task,
    sync_asset_task,
    transcribe_task,
)
from src.infra.broker.media_tasks import media_broker, process_version_task
from src.infra.database.session import create_engine, create_session_factory

from . import OUTBOX_CHANNEL

logger = logging.getLogger(__name__)

_ENRICHMENT = (index_visuals_task, detect_faces_task, annotate_task, transcribe_task)


async def dispatch(event: Event) -> None:
    """Событие → фоновые задачи."""

    match event:
        case AssetVersionAdded():
            await process_version_task.kiq(str(event.version_id))
        case AssetVersionProcessed():
            for task in _ENRICHMENT:
                await task.kiq(str(event.version_id))
        case AssetCurrentVersionChanged() | AssetMoved() | AssetTrashed() | AssetRestored() | AssetPurged():
            await sync_asset_task.kiq(str(event.asset_id))
        case FaceAssigned():
            await propagate_face_task.kiq(str(event.face_id))
        case _:
            logger.warning("No handler for event %s", event.event_type)


async def run_outbox_relay() -> None:
    engine = create_engine(PostgresConfig())
    session_factory = create_session_factory(engine)

    async def publish(events: Sequence[Event]) -> None:
        for event in events:
            await dispatch(event)

    @asynccontextmanager
    async def processor_factory() -> AsyncIterator[OutboxProcessor]:
        async with session_factory() as session:
            yield OutboxProcessor(
                uow=session,
                outbox_store=SqlAlchemyOutboxStore(session),
                publisher=publish,
                config=OutboxConfig(),
            )

    await media_broker.startup()
    await ai_broker.startup()
    logger.info("Outbox relay started")

    try:
        await run_postgres_notify_worker(
            processor_factory,
            PostgresOutboxListener(engine, channel=OUTBOX_CHANNEL),
            OutboxWorkerConfig(),
        )
    finally:
        await ai_broker.shutdown()
        await media_broker.shutdown()
        await engine.dispose()


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_outbox_relay())

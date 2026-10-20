"""
Задачи очереди ``ai``. Запуск: ``taskiq worker src.infra.broker.ai_tasks:ai_broker``.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from taskiq import TaskiqDepends, TaskiqEvents, TaskiqState

from src.application.people.usecases import detect_faces, propagate_face_assignment
from src.application.processing.usecases import annotate_version, transcribe_version
from src.application.search.indexing import index_version_visuals, sync_asset_index
from src.infra.ai.annotator import OpenAIImageAnnotator, VisionConfig, create_openai_client
from src.infra.ai.infinity import InfinityClipEmbedder, InfinityConfig
from src.infra.ai.whisper import WhisperConfig, WhisperTranscriber
from src.infra.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyAssetVersionRepository,
    SqlAlchemyFaceRepository,
    SqlAlchemyTranscriptRepository,
)
from src.infra.media.faces import FacesConfig, OpenCvFaceAnalyzer
from src.infra.qdrant import QdrantConfig, QdrantFaceIndex, QdrantVisualIndex, create_qdrant_client

from .brokers import ai_broker
from .resources import WorkerResources, create_worker_resources


@dataclass(slots=True)
class AiResources:
    qdrant: AsyncQdrantClient
    visual_index: QdrantVisualIndex
    face_index: QdrantFaceIndex
    embedder: InfinityClipEmbedder
    analyzer: OpenCvFaceAnalyzer
    openai: AsyncOpenAI
    annotator: OpenAIImageAnnotator
    transcriber: WhisperTranscriber


@ai_broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    logging.basicConfig(level=logging.INFO)

    qdrant_config = QdrantConfig()
    qdrant = create_qdrant_client(qdrant_config)
    visual_index = QdrantVisualIndex(qdrant, qdrant_config)
    face_index = QdrantFaceIndex(qdrant, qdrant_config)
    await visual_index.ensure_collection()
    await face_index.ensure_collection()

    vision_config = VisionConfig()
    openai = create_openai_client(vision_config)

    state.resources = create_worker_resources()
    state.ai = AiResources(
        qdrant=qdrant,
        visual_index=visual_index,
        face_index=face_index,
        embedder=InfinityClipEmbedder(InfinityConfig()),
        analyzer=OpenCvFaceAnalyzer(FacesConfig()),
        openai=openai,
        annotator=OpenAIImageAnnotator(openai, vision_config),
        transcriber=WhisperTranscriber(WhisperConfig()),
    )


@ai_broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    ai: AiResources = state.ai
    await ai.embedder.close()
    await ai.openai.close()
    await ai.qdrant.close()
    await state.resources.close()


@ai_broker.task(task_name="ai.index_visuals", retry_on_error=True)
async def index_visuals_task(version_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await index_version_visuals(
            UUID(version_id),
            asset_repository=SqlAlchemyAssetRepository(session),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            renditions=resources.renditions,
            processor=resources.processor,
            embedder=ai.embedder,
            visual_index=ai.visual_index,
            uow=session,
        )


@ai_broker.task(task_name="ai.detect_faces", retry_on_error=True)
async def detect_faces_task(version_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await detect_faces(
            UUID(version_id),
            asset_repository=SqlAlchemyAssetRepository(session),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            face_repository=SqlAlchemyFaceRepository(session),
            renditions=resources.renditions,
            processor=resources.processor,
            analyzer=ai.analyzer,
            face_index=ai.face_index,
            uow=session,
        )


@ai_broker.task(task_name="ai.annotate", retry_on_error=True)
async def annotate_task(version_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await annotate_version(
            UUID(version_id),
            asset_repository=SqlAlchemyAssetRepository(session),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            renditions=resources.renditions,
            processor=resources.processor,
            annotator=ai.annotator,
            uow=session,
        )


@ai_broker.task(task_name="ai.transcribe", retry_on_error=True)
async def transcribe_task(version_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await transcribe_version(
            UUID(version_id),
            version_repository=SqlAlchemyAssetVersionRepository(session),
            transcript_repository=SqlAlchemyTranscriptRepository(session),
            renditions=resources.renditions,
            transcriber=ai.transcriber,
            uow=session,
        )


@ai_broker.task(task_name="ai.sync_asset", retry_on_error=True)
async def sync_asset_task(asset_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await sync_asset_index(
            UUID(asset_id),
            asset_repository=SqlAlchemyAssetRepository(session),
            visual_index=ai.visual_index,
            face_index=ai.face_index,
            uow=session,
        )


@ai_broker.task(task_name="ai.propagate_face", retry_on_error=True)
async def propagate_face_task(face_id: str, state: TaskiqState = TaskiqDepends()) -> None:  # noqa: B008
    resources: WorkerResources = state.resources
    ai: AiResources = state.ai

    async with resources.session() as session:
        await propagate_face_assignment(
            UUID(face_id),
            face_repository=SqlAlchemyFaceRepository(session),
            analyzer=ai.analyzer,
            face_index=ai.face_index,
            uow=session,
        )


__all__ = [
    "ai_broker",
    "annotate_task",
    "detect_faces_task",
    "index_visuals_task",
    "propagate_face_task",
    "sync_asset_task",
    "transcribe_task",
]

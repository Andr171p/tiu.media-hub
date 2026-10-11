from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import DBSession
from src.core.common.schemas import QueuedResponse
from src.modules.assets import versions
from src.worker.indexing import reindex_all
from src.worker.processing import process_version, verify_all, verify_integrity

router = APIRouter(tags=["Admin: Maintenance"])


@router.post(
    "/search/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Переиндексировать все активы",
    description="После смены модели эмбеддингов или поколения индекса. Автотеги пересчитываются.",
)
async def reindex_search() -> QueuedResponse:
    await reindex_all.kiq()
    return QueuedResponse(task=reindex_all.task_name)


@router.post(
    "/integrity/verify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Проверить целостность хранилища",
    description="Сверяет SHA-256 каждого оригинала с подтверждённым при загрузке (fixity check).",
)
async def verify_storage() -> QueuedResponse:
    await verify_all.kiq()
    return QueuedResponse(task=verify_all.task_name)


@router.post(
    "/integrity/objects/{object_id}/verify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Проверить целостность объекта",
)
async def verify_object(object_id: UUID) -> QueuedResponse:
    await verify_integrity.kiq(str(object_id))
    return QueuedResponse(task=verify_integrity.task_name)


@router.post(
    "/versions/{version_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Повторить обработку версии",
    description="Для версии, отклонённой при обработке: например, после изменения политики коллекции.",
)
async def reprocess_version(db: DBSession, version_id: UUID) -> QueuedResponse:
    await versions.reset_for_reprocessing(db, version_id)
    await db.commit()
    await process_version.kiq(str(version_id))
    return QueuedResponse(task=process_version.task_name)

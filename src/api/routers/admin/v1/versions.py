from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import OutboxDep, UnitOfWorkDep
from src.api.dependencies.repositories import VersionRepositoryDep
from src.application.processing.usecases import reprocess_version

router = APIRouter(prefix="/versions", tags=["Администрирование"])


@router.post(
    "/{version_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Обработать версию заново",
    description="Превью, прокси и анализ для поиска будут пересозданы в фоне.",
)
async def reprocess(
    version_id: UUID, auth: CurrentUser, versions: VersionRepositoryDep, outbox: OutboxDep, uow: UnitOfWorkDep
) -> None:
    await reprocess_version(version_id, auth, version_repository=versions, outbox=outbox, uow=uow)

from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import OutboxDep, UnitOfWorkDep
from src.api.dependencies.repositories import (
    AssetQueryRepositoryDep,
    AssetRepositoryDep,
    CollectionRepositoryDep,
    CommentRepositoryDep,
    FaceRepositoryDep,
    PersonRepositoryDep,
    TranscriptRepositoryDep,
    UploadRepositoryDep,
    VersionRepositoryDep,
)
from src.api.dependencies.services import EditQueueDep, MediaUrlsDep, OriginalsDep, RenditionsDep
from src.application import comments, editing
from src.application.assets import uploads, usecases
from src.application.assets.dtos import (
    AssetListQuery,
    AssetResponse,
    AssetSummary,
    DownloadResponse,
    MoveAssetDTO,
    UpdateAssetDTO,
    VersionResponse,
)
from src.application.dtos import CursorPage
from src.application.people import usecases as people
from src.application.people.dtos import FaceResponse

router = APIRouter(tags=["Активы"])


# =========================================================================================================
# Загрузка
# =========================================================================================================


@router.post(
    "/uploads",
    status_code=status.HTTP_201_CREATED,
    tags=["Загрузка"],
    summary="Начать загрузку",
    description=(
        "Возвращает presigned URL: файл загружается напрямую в хранилище (PUT). "
        "Большие файлы — частями (multipart): ETag каждой части передайте в complete."
    ),
)
async def start_upload(
    dto: uploads.StartUploadDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    upload_repository: UploadRepositoryDep,
    originals: OriginalsDep,
    uow: UnitOfWorkDep,
) -> uploads.UploadTicket:
    return await uploads.start_upload(
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        upload_repository=upload_repository,
        originals=originals,
        uow=uow,
    )


@router.post(
    "/uploads/{upload_id}/complete",
    tags=["Загрузка"],
    summary="Завершить загрузку",
    description="Создаёт актив или новую версию. Повторный вызов возвращает тот же результат.",
)
async def complete_upload(
    upload_id: UUID,
    dto: uploads.CompleteUploadDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    upload_repository: UploadRepositoryDep,
    originals: OriginalsDep,
    media_urls: MediaUrlsDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> AssetResponse:
    return await uploads.complete_upload(
        upload_id,
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        upload_repository=upload_repository,
        originals=originals,
        media_urls=media_urls,
        outbox=outbox,
        uow=uow,
    )


@router.delete(
    "/uploads/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Загрузка"],
    summary="Отменить загрузку",
)
async def abort_upload(
    upload_id: UUID,
    auth: CurrentUser,
    upload_repository: UploadRepositoryDep,
    originals: OriginalsDep,
    uow: UnitOfWorkDep,
) -> None:
    await uploads.abort_upload(
        upload_id, auth, upload_repository=upload_repository, originals=originals, uow=uow
    )


# =========================================================================================================
# Активы
# =========================================================================================================


@router.get("/assets", summary="Список активов", description="Курсорная пагинация, новые первыми.")
async def list_assets(
    query: Annotated[AssetListQuery, Query()],
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    asset_queries: AssetQueryRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
) -> CursorPage[AssetSummary]:
    return await usecases.list_assets(
        query,
        auth,
        collection_repository=collections,
        asset_query_repository=asset_queries,
        version_repository=versions,
        media_urls=media_urls,
    )


@router.get("/assets/{asset_id}", summary="Актив")
async def get_asset(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
) -> AssetResponse:
    return await usecases.get_asset(
        asset_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        media_urls=media_urls,
    )


@router.patch(
    "/assets/{asset_id}",
    summary="Изменить описание, теги, метаданные, лицензию",
    description="Частичное обновление: явный null очищает description и license.",
)
async def update_asset(
    asset_id: UUID,
    dto: UpdateAssetDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
    uow: UnitOfWorkDep,
) -> AssetResponse:
    return await usecases.update_asset(
        asset_id,
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        media_urls=media_urls,
        uow=uow,
    )


@router.post(
    "/assets/{asset_id}/move", status_code=status.HTTP_204_NO_CONTENT, summary="Перенести в коллекцию"
)
async def move_asset(
    asset_id: UUID,
    dto: MoveAssetDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.move_asset(
        asset_id,
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        outbox=outbox,
        uow=uow,
    )


@router.post("/assets/{asset_id}/trash", status_code=status.HTTP_204_NO_CONTENT, summary="В корзину")
async def trash_asset(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.trash_asset(
        asset_id, auth, asset_repository=assets, collection_repository=collections, outbox=outbox, uow=uow
    )


@router.post("/assets/{asset_id}/restore", status_code=status.HTTP_204_NO_CONTENT, summary="Восстановить")
async def restore_asset(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.restore_asset(
        asset_id, auth, asset_repository=assets, collection_repository=collections, outbox=outbox, uow=uow
    )


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить из корзины навсегда",
    description="Право manage. Корзина очищается автоматически через 30 дней.",
)
async def purge_asset(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    originals: OriginalsDep,
    renditions: RenditionsDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.purge_asset(
        asset_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        originals=originals,
        renditions=renditions,
        outbox=outbox,
        uow=uow,
    )


@router.get(
    "/assets/{asset_id}/download",
    summary="Ссылка на оригинал",
    description="Временная ссылка: файл скачивается напрямую из хранилища.",
)
async def download_asset(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    originals: OriginalsDep,
    version_id: UUID | None = None,
) -> DownloadResponse:
    return await usecases.get_download_url(
        asset_id,
        version_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        originals=originals,
    )


@router.get("/assets/{asset_id}/transcript", summary="Расшифровка речи (видео, аудио)")
async def get_transcript(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    transcripts: TranscriptRepositoryDep,
) -> usecases.TranscriptResponse:
    return await usecases.get_transcript(
        asset_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        transcript_repository=transcripts,
    )


# =========================================================================================================
# Версии
# =========================================================================================================


@router.get("/assets/{asset_id}/versions", tags=["Версии"], summary="История версий")
async def list_versions(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    media_urls: MediaUrlsDep,
) -> list[VersionResponse]:
    return await usecases.list_versions(
        asset_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        media_urls=media_urls,
    )


@router.post(
    "/assets/{asset_id}/versions/{version_id}/make-current",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Версии"],
    summary="Сделать версию текущей",
)
async def make_version_current(
    asset_id: UUID,
    version_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.make_version_current(
        asset_id,
        version_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        outbox=outbox,
        uow=uow,
    )


@router.post(
    "/assets/{asset_id}/edits",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Редактор"],
    summary="Отредактировать изображение",
    description=(
        "Сервер применяет рецепт к оригиналу в полном разрешении и сохраняет результат новой версией "
        "или новым активом. Результат появится по возвращённым идентификаторам после рендера."
    ),
)
async def request_edit(
    asset_id: UUID,
    dto: editing.EditRequestDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    edit_queue: EditQueueDep,
) -> editing.EditAccepted:
    return await editing.request_edit(
        asset_id,
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        edit_queue=edit_queue,
    )


# =========================================================================================================
# Лица и комментарии актива
# =========================================================================================================


@router.get("/assets/{asset_id}/faces", tags=["Люди"], summary="Лица на текущей версии")
async def list_faces(
    asset_id: UUID,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    faces: FaceRepositoryDep,
    people_repository: PersonRepositoryDep,
    media_urls: MediaUrlsDep,
) -> list[FaceResponse]:
    return await people.list_asset_faces(
        asset_id,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        face_repository=faces,
        person_repository=people_repository,
        media_urls=media_urls,
    )


@router.get("/assets/{asset_id}/comments", tags=["Комментарии"], summary="Обсуждения актива")
async def list_comments(
    asset_id: UUID,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
) -> list[comments.CommentResponse]:
    return await comments.list_comments(
        asset_id,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
    )


@router.post(
    "/assets/{asset_id}/comments",
    status_code=status.HTTP_201_CREATED,
    tags=["Комментарии"],
    summary="Начать обсуждение",
    description="Можно отметить область изображения (region) или момент видео (time).",
)
async def create_comment(
    asset_id: UUID,
    dto: comments.CreateCommentDTO,
    auth: CurrentUser,
    comment_repository: CommentRepositoryDep,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    versions: VersionRepositoryDep,
    uow: UnitOfWorkDep,
) -> comments.CommentResponse:
    return await comments.create_comment(
        asset_id,
        dto,
        auth,
        comment_repository=comment_repository,
        asset_repository=assets,
        collection_repository=collections,
        version_repository=versions,
        uow=uow,
    )

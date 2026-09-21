from uuid import UUID

from fastapi import APIRouter, status

from src.modules.auth import CurrentUser
from src.modules.database import DBSession
from src.modules.media import (
    CreateUploadDTO,
    StoredObjectResponse,
    UploadResponse,
    build_object_response,
    object_depends,
    uploading,
)

router = APIRouter(prefix="/media", tags=["Media"])


@router.post(
    "/uploads",
    status_code=status.HTTP_201_CREATED,
    summary="Инициация direct S3 upload",
)
async def create_upload(db: DBSession, dto: CreateUploadDTO, user: CurrentUser) -> UploadResponse:
    upload = uploading.create_upload(db, dto, user_id=user.id)
    await db.commit()
    return upload


@router.post(
    "/uploads/{upload_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Подтвердить загрузку",
)
async def complete_upload(
    db: DBSession,
    upload_id: UUID,
    user: CurrentUser,
) -> StoredObjectResponse:
    obj = await uploading.complete_upload(db, upload_id, user_id=user.id)
    await db.commit()
    return build_object_response(obj)


@router.get(
    "/objects/{object_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить сохранённый объект",
)
async def get_stored_object(obj: StoredObjectResponse = object_depends) -> StoredObjectResponse:
    return obj


@router.get(
    "/objects/{object_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Скачать объект S3 direct-download",
)
async def download_object(): ...

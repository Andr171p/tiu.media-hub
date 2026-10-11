from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import CurrentUser, DBSession, S3Dep, UploadConfigDep
from src.modules import media
from src.modules.media import CreateUploadDTO, StoredObjectResponse, UploadResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Начать загрузку файла",
    description=(
        "Возвращает presigned URL для прямой загрузки в хранилище. SHA-256 входит в подпись: "
        "хранилище отклонит файл, содержимое которого не совпадает с заявленным."
    ),
)
async def create_upload(
    db: DBSession,
    s3: S3Dep,
    config: UploadConfigDep,
    user: CurrentUser,
    dto: CreateUploadDTO,
) -> UploadResponse:
    upload = await media.create_upload(db, s3, config, dto, user_id=user.user.id)
    await db.commit()
    return upload


@router.post(
    "/{upload_id}/complete",
    summary="Подтвердить загрузку",
    description="Сверяет размер и SHA-256 загруженного файла. Повторный вызов возвращает тот же объект.",
)
async def complete_upload(
    db: DBSession, s3: S3Dep, user: CurrentUser, upload_id: UUID
) -> StoredObjectResponse:
    obj = await media.complete_upload(db, s3, upload_id, user_id=user.user.id)
    await db.commit()
    return StoredObjectResponse.model_validate(obj)

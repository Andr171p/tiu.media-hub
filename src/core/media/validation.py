from uuid import UUID

from fastapi import HTTPException, status

from src.core.s3.client import ObjectMeta

from .exceptions import InvalidUploadError
from .models import UploadSession, UploadStatus


def validate_uploaded_object(upload: UploadSession, obj_meta: ObjectMeta) -> None:
    """Проверяет фактические данные с заявленными."""

    if upload.size_bytes != obj_meta.size:
        raise InvalidUploadError("The stated size does not match the actual size.")

    if upload.sha256 != obj_meta.checksum:
        raise InvalidUploadError("The declared hash does not match the actual hash.")


def validate_upload_ownership(upload: UploadSession, user_id: UUID | None) -> None:
    """Проверяет, является ли пользователь владельцем сессии загрузки."""
    if upload.uploaded_by is not None and upload.uploaded_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access the upload db.",
        )


def is_valid_upload_status_to_complete(upload: UploadSession) -> bool:
    """Проверяет статус загрузочной сессии для её завершения."""

    if upload.status == UploadStatus.COMPLETED:
        return True

    if upload.status != UploadStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete upload db. Invalid status: {upload.status}.",
        )

    return False

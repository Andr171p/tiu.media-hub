from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.core.media.crud import get_object, get_user_object
from src.core.media.dtos import StoredObjectResponse
from src.core.media.models import StoredObject
from src.modules.auth import CurrentUser
from src.modules.cdn import cdn_client
from src.modules.database import DBSession


def build_object_response(obj: StoredObject) -> StoredObjectResponse:
    cdn_url = cdn_client.url(...)
    return StoredObjectResponse(
        id=obj.id,
        url=cdn_url,
        content_type=obj.content_type,
        size_bytes=obj.size_bytes,
    )


async def get_object_or_404(db: DBSession, object_id: UUID) -> StoredObjectResponse:
    if (obj := await get_object(db, object_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID {object_id!r} not found.",
        )

    return build_object_response(obj)


async def get_user_object_or_404(
        db: DBSession, object_id: UUID, user: CurrentUser,
) -> StoredObject:
    if (obj := await get_user_object(db, object_id, user.id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Object with ID {object_id!r} not found.",
        )

    return build_object_response(obj)


object_depends = Depends(get_object_or_404)
user_object_depends = Depends(get_user_object_or_404)

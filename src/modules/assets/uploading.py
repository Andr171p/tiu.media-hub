from uuid import UUID

from src.consts import UPLOAD_URL_EXPIRES_IN
from src.core.assets.helpers import build_upload_storage_key, generate_upload_id
from src.core.assets.schemas import UploadFileDTO, UploadFileResponse, UploadInfo
from src.modules.s3 import s3_client


async def init_upload(asset_id: UUID, dto: UploadFileDTO) -> UploadFileResponse:
    upload_id = generate_upload_id(
        asset_id=asset_id,
        filename=dto.filename,
        mime_type=dto.mime_type,
        size=dto.size,
    )
    storage_key = build_upload_storage_key(
        asset_id=asset_id, upload_id=upload_id, filename=dto.filename,
    )

    upload_url = await s3_client.create_upload_url(
        storage_key=storage_key,
        mime_type=dto.mime_type,
        expires_in=UPLOAD_URL_EXPIRES_IN,
    )

    # Запуск Temporal workflow ...

    return UploadFileResponse(
        uploadId=upload_id,
        upload=UploadInfo(url=upload_url, expiresIn=UPLOAD_URL_EXPIRES_IN),
    )


async def confirm_upload(): ...

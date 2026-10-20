"""
Редактор изображений. Фронт собирает рецепт и показывает предпросмотр на canvas,
сервер применяет рецепт к оригиналу: результат в полном разрешении, исходник не меняется.

Порядок операций рецепта: поворот и отражение → кадрирование → размер → коррекция → фильтр → текст.
Координаты кадрирования и текста — доли кадра после поворота.
"""

from typing import Literal, Protocol

import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork
from ddf.domain.exceptions import InvariantViolationError
from pydantic import Field

from src.application.assets.access import get_asset_access
from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser
from src.application.collections.access import get_collection_access
from src.application.collections.repositories import CollectionRepository
from src.application.dtos import CamelModel
from src.application.outbox import save_events_to_outbox
from src.application.storage import FileStorage
from src.domain.assets import AssetKind, StoredFile
from src.domain.assets import logic as assets
from src.domain.collections import Permission


class CropDTO(CamelModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class ResizeDTO(CamelModel):
    """Вписать в рамку с сохранением пропорций; увеличение не выполняется."""

    width: int | None = Field(default=None, ge=1, le=16000)
    height: int | None = Field(default=None, ge=1, le=16000)


class AdjustmentsDTO(CamelModel):
    """Коррекция от -1 до 1, где 0 — без изменений."""

    brightness: float = Field(default=0, ge=-1, le=1)
    contrast: float = Field(default=0, ge=-1, le=1)
    saturation: float = Field(default=0, ge=-1, le=1)


class TextLayerDTO(CamelModel):
    text: str = Field(min_length=1, max_length=500)
    x: float = Field(ge=0, le=1, description="Центр текста, доля ширины")
    y: float = Field(ge=0, le=1, description="Центр текста, доля высоты")
    size: float = Field(default=0.06, gt=0, le=0.5, description="Высота шрифта, доля высоты кадра")
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    bold: bool = False
    shadow: bool = Field(default=True, description="Тень для читаемости на фото")


type Filter = Literal["none", "grayscale", "sepia", "warm", "cool", "vintage"]


class EditRecipe(CamelModel):
    rotate: Literal[0, 90, 180, 270] = Field(default=0, description="Градусы по часовой стрелке")
    flip_horizontal: bool = False
    flip_vertical: bool = False
    crop: CropDTO | None = None
    resize: ResizeDTO | None = None
    adjustments: AdjustmentsDTO = Field(default_factory=AdjustmentsDTO)
    filter: Filter = "none"
    texts: list[TextLayerDTO] = Field(default_factory=list, max_length=20)
    format: Literal["jpeg", "png", "webp"] = "jpeg"
    quality: int = Field(default=90, ge=50, le=100)


class EditRequestDTO(CamelModel):
    recipe: EditRecipe
    source_version_id: UUID | None = Field(default=None, description="По умолчанию — текущая версия")
    save_as: Literal["version", "asset"] = Field(description="Новая версия этого актива или отдельный актив")
    title: str | None = Field(default=None, max_length=500, description="Название нового актива")
    collection_id: UUID | None = Field(
        default=None, description="Коллекция нового актива (по умолчанию та же)"
    )


class EditJob(CamelModel):
    """Задание рендера. Идентификаторы выданы заранее: повтор задания не создаст дубликат."""

    asset_id: UUID
    version_id: UUID
    source_version_id: UUID
    user_id: UUID
    recipe: EditRecipe
    save_as: Literal["version", "asset"]
    collection_id: UUID
    title: str | None = None


class EditAccepted(CamelModel):
    asset_id: UUID = Field(description="Актив, в котором появится результат")
    version_id: UUID = Field(description="Версия-результат: появится после рендера")


class ImageEditor(Protocol):
    async def render(self, source: Path, recipe: EditRecipe, output: Path) -> str:
        """Применяет рецепт и возвращает MIME-тип результата."""


class EditQueue(Protocol):
    async def enqueue(self, job: EditJob) -> None: ...


_EXTENSIONS = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}


async def request_edit(
    asset_id: UUID,
    dto: EditRequestDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    edit_queue: EditQueue,
) -> EditAccepted:
    access = await get_asset_access(
        asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )
    if access.asset.kind is not AssetKind.IMAGE:
        raise InvariantViolationError("Only images can be edited.")

    source_version_id = dto.source_version_id or access.asset.current_version_id
    source = await version_repository.read(source_version_id)
    if source is None or source.asset_id != asset_id:
        raise NotFoundError(f"Version with ID {source_version_id} not found.")

    collection_id = access.asset.collection_id
    if dto.save_as == "asset" and dto.collection_id and dto.collection_id != collection_id:
        await get_collection_access(
            dto.collection_id, auth, Permission.WRITE, collection_repository=collection_repository
        )
        collection_id = dto.collection_id

    job = EditJob(
        asset_id=asset_id if dto.save_as == "version" else uuid.uuid7(),
        version_id=uuid.uuid7(),
        source_version_id=source.id,
        user_id=auth.user_id,
        recipe=dto.recipe,
        save_as=dto.save_as,
        collection_id=collection_id,
        title=dto.title,
    )
    await edit_queue.enqueue(job)

    return EditAccepted(asset_id=job.asset_id, version_id=job.version_id)


async def render_edit(
    job: EditJob,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    version_repository: AssetVersionRepository,
    originals: FileStorage,
    editor: ImageEditor,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    """Рендерит правку и сохраняет её новой версией или новым активом (фоновая задача)."""

    if await version_repository.read(job.version_id) is not None:
        return

    source = await version_repository.read(job.source_version_id)
    await uow.rollback()
    if source is None:
        return

    with TemporaryDirectory(prefix="dam-edit-") as tmp:
        source_path, output = Path(tmp) / "source", Path(tmp) / "result"
        await originals.download_file(source.file.key, source_path)
        content_type = await editor.render(source_path, job.recipe, output)

        extension = _EXTENSIONS[job.recipe.format]
        file = StoredFile(
            key=f"{datetime.now(UTC):%Y/%m}/{job.version_id}{extension}",
            name=f"{PurePath(source.file.name).stem}-edit{extension}",
            content_type=content_type,
            size=output.stat().st_size,
        )
        await originals.upload_file(file.key, output, content_type)

    if job.save_as == "version":
        asset = await asset_repository.read(job.asset_id, with_lock=True)
        if asset is None:
            return
        version = asset.add_version(
            file,
            created_by=job.user_id,
            source_version_id=source.id,
            note="Редактор",
            version_id=job.version_id,
        )
        await asset_repository.update(asset)
    else:
        if (collection := await collection_repository.read(job.collection_id)) is None:
            return
        asset, version = assets.create_asset(
            collection,
            file,
            created_by=job.user_id,
            title=job.title,
            source_version_id=source.id,
            asset_id=job.asset_id,
            version_id=job.version_id,
        )
        await asset_repository.create(asset)

    await version_repository.create(version)
    await save_events_to_outbox(outbox, asset)
    await uow.commit()


__all__ = [
    "EditAccepted",
    "EditJob",
    "EditQueue",
    "EditRecipe",
    "EditRequestDTO",
    "ImageEditor",
    "render_edit",
    "request_edit",
]

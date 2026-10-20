from uuid import UUID

from ddf.application.uow import UnitOfWork

from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.people.ports import FaceIndex
from src.application.processing.ports import MediaProcessor
from src.application.processing.usecases import load_frames
from src.application.storage import FileStorage
from src.domain.assets import Asset

from .ports import AssetIndexState, ClipEmbedder, VisualIndex, VisualPoint


def index_state(asset: Asset) -> AssetIndexState:
    return AssetIndexState(
        asset_id=asset.id,
        collection_id=asset.collection_id,
        kind=asset.kind,
        current_version_id=asset.current_version_id,
        trashed=asset.is_deleted,
    )


async def index_version_visuals(
    version_id: UUID,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    renditions: FileStorage,
    processor: MediaProcessor,
    embedder: ClipEmbedder,
    visual_index: VisualIndex,
    uow: UnitOfWork,
) -> None:
    """CLIP-векторы кадров версии: поиск по описанию и по похожему изображению."""

    version = await version_repository.read(version_id)
    asset = await asset_repository.read(version.asset_id) if version else None
    await uow.rollback()

    if version is None or asset is None:
        return

    frames = await load_frames(version, renditions=renditions, processor=processor)
    if not frames:
        return

    vectors = await embedder.embed_images([frame.image for frame in frames])
    points = [
        VisualPoint(vector=vector, version_id=version.id, timecode=frame.timecode)
        for frame, vector in zip(frames, vectors, strict=True)
    ]
    await visual_index.replace_version(index_state(asset), points)


async def sync_asset_index(
    asset_id: UUID,
    *,
    asset_repository: AssetRepository,
    visual_index: VisualIndex,
    face_index: FaceIndex,
    uow: UnitOfWork,
) -> None:
    """Приводит видимость векторов актива к его состоянию: перенос, корзина, смена версии, удаление."""

    asset = await asset_repository.read(asset_id)
    await uow.rollback()

    if asset is None:
        await visual_index.delete_asset(asset_id)
        await face_index.delete_asset(asset_id)
        return

    state = index_state(asset)
    await visual_index.sync_asset(state)
    await face_index.sync_asset(state)


__all__ = ["index_state", "index_version_visuals", "sync_asset_index"]

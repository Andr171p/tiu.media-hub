import logging
import math
from collections.abc import Sequence
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload, undefer

from src.core.infinity import ImageInput, InfinityClient, Vector
from src.core.s3 import S3Client, S3NotFoundError
from src.modules.assets import Asset, AssetStatus, AssetVersion, RenditionKind
from src.modules.tags import AssetTag, apply_auto_tags, autotag_prompt, list_auto_tags

from .config import SearchConfig
from .index import AssetPoint, AssetSearchIndex

logger = logging.getLogger(__name__)

_TAG_CANDIDATES = 50


def _flatten(value: JsonValue) -> list[str]:
    if isinstance(value, list):
        return [item for nested in value for item in _flatten(nested)]
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _flatten(nested)]
    return [] if value is None or isinstance(value, bool) else [str(value)]


def build_search_text(asset: Asset, version: AssetVersion | None, tags: Sequence[str]) -> str:
    """Текст для BM25: всё, по чему пользователь может искать актив словами."""

    parts: list[str | None] = [asset.title, asset.description, *tags, *_flatten(asset.custom_meta)]

    if asset.license is not None:
        parts.extend([asset.license.holder, asset.license.author])

    if version is not None:
        parts.append(version.original_filename)
        if (embedded := getattr(version.meta, "embedded", None)) is not None:
            parts.extend([embedded.title, embedded.description, embedded.creator, *embedded.keywords])
        parts.append(version.extracted_text)

    return "\n".join(part for part in parts if part)


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


class AssetIndexer:
    """Синхронизирует индекс поиска и автотеги с PostgreSQL. Все операции идемпотентны."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        s3: S3Client,
        embedder: InfinityClient,
        index: AssetSearchIndex,
        config: SearchConfig,
    ) -> None:
        self._sessions = sessions
        self._s3 = s3
        self._embedder = embedder
        self._index = index
        self._config = config

    async def _load(self, session: AsyncSession, asset_id: UUID) -> Asset | None:
        return await session.scalar(
            select(Asset)
            .where(
                Asset.id == asset_id,
                Asset.deleted_at.is_(None),
                Asset.status == AssetStatus.ACTIVE,
            )
            .options(
                selectinload(Asset.tags).selectinload(AssetTag.tag),
                selectinload(Asset.current_version).options(
                    selectinload(AssetVersion.renditions),
                    undefer(AssetVersion.extracted_text),
                ),
            )
            .execution_options(populate_existing=True),
        )

    async def _embed_thumbnail(self, version: AssetVersion) -> Vector | None:
        thumbnail = next((item for item in version.renditions if item.kind is RenditionKind.THUMBNAIL), None)
        if thumbnail is None:
            return None
        try:
            content = await self._s3.read(thumbnail.storage_key)
        except S3NotFoundError:
            logger.warning("Thumbnail %s is missing, asset is indexed without image", thumbnail.storage_key)
            return None
        return await self._embedder.embed_image(
            ImageInput(content=content, content_type=thumbnail.content_type)
        )

    async def _auto_tag(self, session: AsyncSession, asset_id: UUID, image_vector: Vector) -> None:
        """Zero-shot классификация: близость эмбеддинга изображения к эмбеддингам тегов словаря."""

        config = self._config
        candidates = await self._index.score_tags(image_vector, limit=_TAG_CANDIDATES)

        scored = [
            (tag_id, round(probability, 4))
            for tag_id, similarity in candidates
            if (probability := _sigmoid(config.autotag_logit_scale * similarity + config.autotag_logit_bias))
            >= config.autotag_min_probability
        ][: config.autotag_max_tags]

        await apply_auto_tags(session, asset_id, scored)

    async def index_asset(self, asset_id: UUID, *, with_image: bool) -> None:
        """
        Индексирует актив по текущей версии. ``with_image`` — пересчитать эмбеддинг и автотеги
        (новая версия); иначе обновляется только текст (изменились название, теги, метаданные).
        """

        async with self._sessions() as session, session.begin():
            asset = await self._load(session, asset_id)
            if asset is None:
                await self._index.delete(asset_id)
                return

            version = asset.current_version
            if version is None:
                image_vector = None
            elif with_image:
                image_vector = await self._embed_thumbnail(version)
            else:
                # Эмбеддинг не зависит от текста: берём посчитанный при прошлой индексации
                image_vector = await self._index.get_image_vector(asset.id)

            if with_image and image_vector is not None:
                await self._auto_tag(session, asset.id, image_vector)
                if (asset := await self._load(session, asset_id)) is None:
                    return

            tags = sorted(item.tag.name for item in asset.tags)
            await self._index.upsert(
                AssetPoint(
                    asset_id=asset.id,
                    collection_id=asset.collection_id,
                    kind=asset.kind.value,
                    tags=tags,
                    text=build_search_text(asset, version, tags),
                    image_vector=image_vector,
                ),
            )

    async def remove_asset(self, asset_id: UUID) -> None:
        await self._index.delete(asset_id)

    async def remove_collection(self, collection_id: UUID) -> None:
        await self._index.delete_collection_assets(collection_id)

    async def sync_tag_vocabulary(self) -> int:
        """Пересчитывает эмбеддинги тегов автотегирования."""

        async with self._sessions() as session:
            tags = await list_auto_tags(session)

        prompts = [self._config.autotag_prompt_template.format(tag=autotag_prompt(tag)) for tag in tags]
        vectors = await self._embedder.embed_texts(prompts) if prompts else []
        await self._index.replace_tags([(tag.id, vector) for tag, vector in zip(tags, vectors, strict=True)])
        return len(tags)

    async def asset_ids(self) -> Sequence[UUID]:
        async with self._sessions() as session:
            stmt = select(Asset.id).where(
                Asset.deleted_at.is_(None),
                Asset.status == AssetStatus.ACTIVE,
                Asset.current_version_id.is_not(None),
            )
            return (await session.scalars(stmt)).all()


__all__ = ["AssetIndexer", "build_search_text"]

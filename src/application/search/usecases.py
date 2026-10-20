from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from ddf.domain.exceptions import InvariantViolationError

from src.application.assets.presenters import present_summaries
from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser
from src.application.collections.access import readable_collection_ids
from src.application.collections.repositories import CollectionRepository
from src.application.people.ports import FaceAnalyzer, FaceIndex
from src.application.storage import MediaUrls

from .dtos import MatchSource, SearchFilters, SearchHit, SearchMatch, SearchResponse, TextSearchDTO
from .ports import ClipEmbedder, SearchScope, TextSearchRepository, VisualHit, VisualIndex

RRF_K = 60
# Сходство CLIP менее точно, чем совпадение в описании или речи: визуальные совпадения весят меньше
VISUAL_WEIGHT = 0.5
MAX_MATCHES = 5


@dataclass
class _Ranked:
    score: float = 0.0
    matches: list[SearchMatch] = field(default_factory=list)


async def _scope(
    filters: SearchFilters, auth: AuthUser, *, collection_repository: CollectionRepository
) -> SearchScope:
    readable = await readable_collection_ids(auth, collection_repository=collection_repository)

    collection_ids: list[UUID] | None = readable
    if filters.collection_ids:
        allowed = None if readable is None else set(readable)
        collection_ids = [cid for cid in filters.collection_ids if allowed is None or cid in allowed]

    return SearchScope(collection_ids=collection_ids, kinds=filters.kinds)


def _add_visual(
    ranked: dict[UUID, _Ranked], hits: Sequence[VisualHit], *, weight: float = VISUAL_WEIGHT
) -> None:
    """Кадры одного актива сворачиваются в один результат: ранг по лучшему кадру."""

    by_asset: dict[UUID, list[VisualHit]] = defaultdict(list)
    for hit in hits:
        by_asset[hit.asset_id].append(hit)

    for rank, (asset_id, asset_hits) in enumerate(by_asset.items()):
        item = ranked.setdefault(asset_id, _Ranked())
        item.score += weight / (RRF_K + rank)
        item.matches.extend(
            SearchMatch(source=MatchSource.VISUAL, timecode=hit.timecode) for hit in asset_hits[:MAX_MATCHES]
        )


async def _present(
    ranked: dict[UUID, _Ranked],
    limit: int,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    media_urls: MediaUrls,
) -> SearchResponse:
    top = sorted(ranked.items(), key=lambda item: item[1].score, reverse=True)[:limit]
    assets = {
        asset.id: asset
        for asset in await asset_repository.get_by_ids([asset_id for asset_id, _ in top])
        if not asset.is_deleted
    }
    ordered = [assets[asset_id] for asset_id, _ in top if asset_id in assets]
    summaries = await present_summaries(ordered, version_repository=version_repository, media_urls=media_urls)

    return SearchResponse(
        items=[
            SearchHit(asset=summary, score=ranked[summary.id].score, matches=ranked[summary.id].matches)
            for summary in summaries
        ]
    )


async def search_assets(
    dto: TextSearchDTO,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    embedder: ClipEmbedder,
    visual_index: VisualIndex,
    text_search: TextSearchRepository,
    media_urls: MediaUrls,
) -> SearchResponse:
    """Поиск на естественном языке: смысл изображения (CLIP) + текст и речь, объединённые через RRF."""

    scope = await _scope(dto, auth, collection_repository=collection_repository)
    ranked: dict[UUID, _Ranked] = {}

    vector = await embedder.embed_text(dto.query)
    visual = await visual_index.search(
        vector, scope, limit=dto.limit * 3, min_score=embedder.text_match_score
    )
    _add_visual(ranked, visual)

    for rank, hit in enumerate(await text_search.search(dto.query, scope, limit=dto.limit)):
        item = ranked.setdefault(hit.asset_id, _Ranked())
        item.score += 1 / (RRF_K + rank)
        item.matches.append(
            SearchMatch(
                source=MatchSource.SPEECH if hit.timecode is not None else MatchSource.TEXT,
                timecode=hit.timecode,
                snippet=hit.snippet,
            )
        )

    return await _present(
        ranked,
        dto.limit,
        asset_repository=asset_repository,
        version_repository=version_repository,
        media_urls=media_urls,
    )


async def search_by_image(
    image: bytes,
    filters: SearchFilters,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    embedder: ClipEmbedder,
    visual_index: VisualIndex,
    media_urls: MediaUrls,
) -> SearchResponse:
    """Похожие изображения и кадры видео: все ракурсы одного продукта."""

    scope = await _scope(filters, auth, collection_repository=collection_repository)
    [vector] = await embedder.embed_images([image])

    ranked: dict[UUID, _Ranked] = {}
    visual = await visual_index.search(
        vector, scope, limit=filters.limit * 3, min_score=embedder.image_match_score
    )
    _add_visual(ranked, visual, weight=1.0)

    return await _present(
        ranked,
        filters.limit,
        asset_repository=asset_repository,
        version_repository=version_repository,
        media_urls=media_urls,
    )


async def search_by_face(
    image: bytes,
    filters: SearchFilters,
    auth: AuthUser,
    *,
    collection_repository: CollectionRepository,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    analyzer: FaceAnalyzer,
    face_index: FaceIndex,
    media_urls: MediaUrls,
) -> SearchResponse:
    """Поиск по селфи: материалы, где есть человек с самым крупным лицом на снимке."""

    faces = await analyzer.detect(image)
    if not faces:
        raise InvariantViolationError("No face found on the image.")

    face = max(faces, key=lambda item: item.box.width * item.box.height)
    scope = await _scope(filters, auth, collection_repository=collection_repository)
    hits = await face_index.search(
        face.vector, scope, limit=filters.limit * 3, min_score=analyzer.same_person_score
    )

    ranked: dict[UUID, _Ranked] = {}
    for hit in hits:
        item = ranked.setdefault(hit.asset_id, _Ranked())
        item.score = max(item.score, hit.score)
        item.matches.append(SearchMatch(source=MatchSource.FACE))

    return await _present(
        ranked,
        filters.limit,
        asset_repository=asset_repository,
        version_repository=version_repository,
        media_urls=media_urls,
    )


__all__ = ["search_assets", "search_by_face", "search_by_image"]

from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.repositories import (
    AssetRepositoryDep,
    CollectionRepositoryDep,
    TextSearchRepositoryDep,
    VersionRepositoryDep,
)
from src.api.dependencies.services import (
    EmbedderDep,
    FaceAnalyzerDep,
    FaceIndexDep,
    MediaUrlsDep,
    VisualIndexDep,
)
from src.application.search import usecases
from src.application.search.dtos import SearchFilters, SearchResponse, TextSearchDTO
from src.domain.assets import AssetKind

router = APIRouter(prefix="/search", tags=["Поиск"])

MAX_QUERY_IMAGE = 20 * 1024 * 1024


async def _read_image(file: UploadFile) -> bytes:
    data = await file.read(MAX_QUERY_IMAGE + 1)
    if len(data) > MAX_QUERY_IMAGE:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Image is too large.")
    return data


def _filters(collection_ids: list[UUID] | None, kinds: list[AssetKind] | None, limit: int) -> SearchFilters:
    return SearchFilters(collection_ids=collection_ids or [], kinds=kinds or [], limit=limit)


@router.post(
    "",
    summary="Поиск на естественном языке",
    description="«студент получает диплом на сцене»: смысл изображения, описания, теги и речь в видео.",
)
async def search(
    dto: TextSearchDTO,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    assets: AssetRepositoryDep,
    versions: VersionRepositoryDep,
    embedder: EmbedderDep,
    visual_index: VisualIndexDep,
    text_search: TextSearchRepositoryDep,
    media_urls: MediaUrlsDep,
) -> SearchResponse:
    return await usecases.search_assets(
        dto,
        auth,
        collection_repository=collections,
        asset_repository=assets,
        version_repository=versions,
        embedder=embedder,
        visual_index=visual_index,
        text_search=text_search,
        media_urls=media_urls,
    )


@router.post("/by-image", summary="Похожие изображения и кадры видео")
async def search_by_image(
    image: UploadFile,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    assets: AssetRepositoryDep,
    versions: VersionRepositoryDep,
    embedder: EmbedderDep,
    visual_index: VisualIndexDep,
    media_urls: MediaUrlsDep,
    collection_ids: Annotated[list[UUID] | None, Form(alias="collectionIds")] = None,
    kinds: Annotated[list[AssetKind] | None, Form()] = None,
    limit: Annotated[int, Form(ge=1, le=200)] = 60,
) -> SearchResponse:
    return await usecases.search_by_image(
        await _read_image(image),
        _filters(collection_ids, kinds, limit),
        auth,
        collection_repository=collections,
        asset_repository=assets,
        version_repository=versions,
        embedder=embedder,
        visual_index=visual_index,
        media_urls=media_urls,
    )


@router.post(
    "/by-face",
    summary="Поиск по селфи",
    description="Материалы с человеком, чьё лицо крупнее всех на снимке.",
)
async def search_by_face(
    image: UploadFile,
    auth: CurrentUser,
    collections: CollectionRepositoryDep,
    assets: AssetRepositoryDep,
    versions: VersionRepositoryDep,
    analyzer: FaceAnalyzerDep,
    face_index: FaceIndexDep,
    media_urls: MediaUrlsDep,
    collection_ids: Annotated[list[UUID] | None, Form(alias="collectionIds")] = None,
    kinds: Annotated[list[AssetKind] | None, Form()] = None,
    limit: Annotated[int, Form(ge=1, le=200)] = 60,
) -> SearchResponse:
    return await usecases.search_by_face(
        await _read_image(image),
        _filters(collection_ids, kinds, limit),
        auth,
        collection_repository=collections,
        asset_repository=assets,
        version_repository=versions,
        analyzer=analyzer,
        face_index=face_index,
        media_urls=media_urls,
    )

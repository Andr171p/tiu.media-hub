"""Долгоживущие клиенты из lifespan (``app.state``)."""

from typing import Annotated

from fastapi import Depends, Request

from src.application.editing import EditQueue
from src.application.people.ports import FaceAnalyzer, FaceIndex
from src.application.portals.ports import PortalSecrets
from src.application.search.ports import ClipEmbedder, VisualIndex
from src.application.storage import FileStorage, MediaUrls


def get_originals(request: Request) -> FileStorage:
    return request.app.state.originals


def get_renditions(request: Request) -> FileStorage:
    return request.app.state.renditions


def get_media_urls(request: Request) -> MediaUrls:
    return request.app.state.media_urls


def get_embedder(request: Request) -> ClipEmbedder:
    return request.app.state.embedder


def get_visual_index(request: Request) -> VisualIndex:
    return request.app.state.visual_index


def get_face_index(request: Request) -> FaceIndex:
    return request.app.state.face_index


def get_face_analyzer(request: Request) -> FaceAnalyzer:
    return request.app.state.face_analyzer


def get_portal_secrets(request: Request) -> PortalSecrets:
    return request.app.state.portal_secrets


def get_edit_queue(request: Request) -> EditQueue:
    return request.app.state.edit_queue


OriginalsDep = Annotated[FileStorage, Depends(get_originals)]
RenditionsDep = Annotated[FileStorage, Depends(get_renditions)]
MediaUrlsDep = Annotated[MediaUrls, Depends(get_media_urls)]
EmbedderDep = Annotated[ClipEmbedder, Depends(get_embedder)]
VisualIndexDep = Annotated[VisualIndex, Depends(get_visual_index)]
FaceIndexDep = Annotated[FaceIndex, Depends(get_face_index)]
FaceAnalyzerDep = Annotated[FaceAnalyzer, Depends(get_face_analyzer)]
PortalSecretsDep = Annotated[PortalSecrets, Depends(get_portal_secrets)]
EditQueueDep = Annotated[EditQueue, Depends(get_edit_queue)]

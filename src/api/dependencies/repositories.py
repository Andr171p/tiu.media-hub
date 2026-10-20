from typing import Annotated

from fastapi import Depends

from src.application.assets.repositories import (
    AssetQueryRepository,
    AssetRepository,
    AssetVersionRepository,
    UploadRepository,
)
from src.application.collections.repositories import CollectionMemberRepository, CollectionRepository
from src.application.comments import CommentRepository
from src.application.people.repositories import FaceRepository, PersonRepository
from src.application.portals.ports import PortalRepository
from src.application.processing.repositories import TranscriptRepository
from src.application.search.ports import TextSearchRepository
from src.application.selections import SelectionRepository
from src.application.users import UserRepository
from src.infra.database.repositories import (
    SqlAlchemyAssetQueryRepository,
    SqlAlchemyAssetRepository,
    SqlAlchemyAssetVersionRepository,
    SqlAlchemyCollectionMemberRepository,
    SqlAlchemyCollectionRepository,
    SqlAlchemyCommentRepository,
    SqlAlchemyFaceRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemyPortalRepository,
    SqlAlchemySelectionRepository,
    SqlAlchemyTextSearchRepository,
    SqlAlchemyTranscriptRepository,
    SqlAlchemyUploadRepository,
    SqlAlchemyUserRepository,
)

from .db import DBSession


def get_user_repository(session: DBSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_collection_repository(session: DBSession) -> CollectionRepository:
    return SqlAlchemyCollectionRepository(session)


def get_member_repository(session: DBSession) -> CollectionMemberRepository:
    return SqlAlchemyCollectionMemberRepository(session)


def get_asset_repository(session: DBSession) -> AssetRepository:
    return SqlAlchemyAssetRepository(session)


def get_version_repository(session: DBSession) -> AssetVersionRepository:
    return SqlAlchemyAssetVersionRepository(session)


def get_upload_repository(session: DBSession) -> UploadRepository:
    return SqlAlchemyUploadRepository(session)


def get_asset_query_repository(session: DBSession) -> AssetQueryRepository:
    return SqlAlchemyAssetQueryRepository(session)


def get_transcript_repository(session: DBSession) -> TranscriptRepository:
    return SqlAlchemyTranscriptRepository(session)


def get_text_search_repository(session: DBSession) -> TextSearchRepository:
    return SqlAlchemyTextSearchRepository(session)


def get_person_repository(session: DBSession) -> PersonRepository:
    return SqlAlchemyPersonRepository(session)


def get_face_repository(session: DBSession) -> FaceRepository:
    return SqlAlchemyFaceRepository(session)


def get_comment_repository(session: DBSession) -> CommentRepository:
    return SqlAlchemyCommentRepository(session)


def get_selection_repository(session: DBSession) -> SelectionRepository:
    return SqlAlchemySelectionRepository(session)


def get_portal_repository(session: DBSession) -> PortalRepository:
    return SqlAlchemyPortalRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
CollectionRepositoryDep = Annotated[CollectionRepository, Depends(get_collection_repository)]
MemberRepositoryDep = Annotated[CollectionMemberRepository, Depends(get_member_repository)]
AssetRepositoryDep = Annotated[AssetRepository, Depends(get_asset_repository)]
VersionRepositoryDep = Annotated[AssetVersionRepository, Depends(get_version_repository)]
UploadRepositoryDep = Annotated[UploadRepository, Depends(get_upload_repository)]
AssetQueryRepositoryDep = Annotated[AssetQueryRepository, Depends(get_asset_query_repository)]
TranscriptRepositoryDep = Annotated[TranscriptRepository, Depends(get_transcript_repository)]
TextSearchRepositoryDep = Annotated[TextSearchRepository, Depends(get_text_search_repository)]
PersonRepositoryDep = Annotated[PersonRepository, Depends(get_person_repository)]
FaceRepositoryDep = Annotated[FaceRepository, Depends(get_face_repository)]
CommentRepositoryDep = Annotated[CommentRepository, Depends(get_comment_repository)]
SelectionRepositoryDep = Annotated[SelectionRepository, Depends(get_selection_repository)]
PortalRepositoryDep = Annotated[PortalRepository, Depends(get_portal_repository)]

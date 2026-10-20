from dataclasses import dataclass, field
from uuid import UUID

from ddf.application.exceptions import NotFoundError
from ddf.application.outbox import OutboxStore
from ddf.application.uow import UnitOfWork
from ddf.domain.utils import apply_changes

from src.application.assets.access import get_asset_access
from src.application.assets.repositories import AssetRepository, AssetVersionRepository
from src.application.auth import AuthUser, PermissionDeniedError
from src.application.collections.repositories import CollectionRepository
from src.application.outbox import save_events_to_outbox
from src.application.processing.ports import MediaProcessor
from src.application.processing.usecases import load_frames
from src.application.search.indexing import index_state
from src.application.search.ports import SearchScope
from src.application.storage import FileStorage, MediaUrls
from src.domain.collections import Permission
from src.domain.people import Face, Person

from .dtos import AssignFaceDTO, BoxDTO, FaceResponse, PersonDTO, PersonResponse, UpdatePersonDTO
from .ports import DetectedFace, FaceAnalyzer, FaceIndex, FacePoint
from .repositories import FaceRepository, PersonRepository

PROPAGATION_LIMIT = 500


def face_thumbnail_key(face_id: UUID) -> str:
    return f"faces/{face_id}.webp"


# =========================================================================================================
# Справочник людей
# =========================================================================================================


async def _present_people(
    people: list[Person], *, face_repository: FaceRepository, media_urls: MediaUrls
) -> list[PersonResponse]:
    covers = await face_repository.first_confirmed([person.id for person in people])

    return [
        PersonResponse(
            id=person.id,
            name=person.name,
            description=person.description,
            cover_url=media_urls.url(face_thumbnail_key(covers[person.id].id))
            if person.id in covers
            else None,
            created_by=person.created_by,
            created_at=person.created_at,
        )
        for person in people
    ]


async def _read_person(person_id: UUID, *, person_repository: PersonRepository) -> Person:
    if (person := await person_repository.read(person_id)) is None:
        raise NotFoundError(f"Person with ID {person_id} not found.")
    return person


def _ensure_can_edit(person: Person, auth: AuthUser) -> None:
    if person.created_by != auth.user_id and not auth.is_admin:
        raise PermissionDeniedError("Only the author or an administrator can change this person.")


async def create_person(
    dto: PersonDTO, auth: AuthUser, *, person_repository: PersonRepository, uow: UnitOfWork
) -> PersonResponse:
    person = Person(name=dto.name, description=dto.description, created_by=auth.user_id)
    await person_repository.create(person)
    await uow.commit()

    return PersonResponse(
        id=person.id,
        name=person.name,
        description=person.description,
        cover_url=None,
        created_by=person.created_by,
        created_at=person.created_at,
    )


async def list_people(
    query: str | None,
    *,
    person_repository: PersonRepository,
    face_repository: FaceRepository,
    media_urls: MediaUrls,
    limit: int = 200,
) -> list[PersonResponse]:
    people = list(await person_repository.search(query, limit=limit))
    return await _present_people(people, face_repository=face_repository, media_urls=media_urls)


async def get_person(
    person_id: UUID,
    *,
    person_repository: PersonRepository,
    face_repository: FaceRepository,
    media_urls: MediaUrls,
) -> PersonResponse:
    person = await _read_person(person_id, person_repository=person_repository)
    [response] = await _present_people([person], face_repository=face_repository, media_urls=media_urls)
    return response


async def update_person(
    person_id: UUID,
    dto: UpdatePersonDTO,
    auth: AuthUser,
    *,
    person_repository: PersonRepository,
    face_repository: FaceRepository,
    media_urls: MediaUrls,
    uow: UnitOfWork,
) -> PersonResponse:
    person = await _read_person(person_id, person_repository=person_repository)
    _ensure_can_edit(person, auth)

    apply_changes(person, name=dto.name)
    if "description" in dto.model_fields_set:
        person.description = dto.description

    await person_repository.update(person)
    await uow.commit()

    [response] = await _present_people([person], face_repository=face_repository, media_urls=media_urls)
    return response


async def delete_person(
    person_id: UUID,
    auth: AuthUser,
    *,
    person_repository: PersonRepository,
    face_repository: FaceRepository,
    face_index: FaceIndex,
    uow: UnitOfWork,
) -> None:
    person = await _read_person(person_id, person_repository=person_repository)
    _ensure_can_edit(person, auth)

    face_ids = await face_repository.unassign_person(person.id)
    await person_repository.delete(person.id)
    await uow.commit()

    await face_index.set_person(face_ids, None, confirmed=False)


# =========================================================================================================
# Лица на активах
# =========================================================================================================


def _present_face(face: Face, people: dict[UUID, Person], media_urls: MediaUrls) -> FaceResponse:
    person = people.get(face.person_id) if face.person_id else None

    return FaceResponse(
        id=face.id,
        box=BoxDTO.model_validate(face.box),
        timecodes=list(face.timecodes),
        person_id=face.person_id,
        person_name=person.name if person else None,
        confirmed=face.is_confirmed,
        thumbnail_url=media_urls.url(face_thumbnail_key(face.id)),
    )


async def list_asset_faces(
    asset_id: UUID,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    face_repository: FaceRepository,
    person_repository: PersonRepository,
    media_urls: MediaUrls,
) -> list[FaceResponse]:
    """Лица текущей версии актива."""

    access = await get_asset_access(
        asset_id, auth, asset_repository=asset_repository, collection_repository=collection_repository
    )
    faces = await face_repository.list_by_version(access.asset.current_version_id)
    person_ids = [face.person_id for face in faces if face.person_id]
    people = {person.id: person for person in await person_repository.get_by_ids(person_ids)}

    return [_present_face(face, people, media_urls) for face in faces]


async def assign_face(
    face_id: UUID,
    dto: AssignFaceDTO,
    auth: AuthUser,
    *,
    asset_repository: AssetRepository,
    collection_repository: CollectionRepository,
    face_repository: FaceRepository,
    person_repository: PersonRepository,
    media_urls: MediaUrls,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> FaceResponse:
    """Подписывает лицо; похожие лица на других активах распознаются в фоне."""

    if (face := await face_repository.read(face_id)) is None:
        raise NotFoundError(f"Face with ID {face_id} not found.")

    await get_asset_access(
        face.asset_id,
        auth,
        Permission.WRITE,
        asset_repository=asset_repository,
        collection_repository=collection_repository,
    )

    person: Person | None = None
    if dto.person_id is not None:
        person = await _read_person(dto.person_id, person_repository=person_repository)
    elif dto.new_person_name is not None:
        person = Person(name=dto.new_person_name, created_by=auth.user_id)
        await person_repository.create(person)

    face.assign(person.id if person else None, by=auth.user_id)

    await face_repository.update(face)
    await save_events_to_outbox(outbox, face)
    await uow.commit()

    return _present_face(face, {person.id: person} if person else {}, media_urls)


# =========================================================================================================
# Фоновое распознавание
# =========================================================================================================


@dataclass
class _Cluster:
    """Появления одного человека в разных кадрах видео."""

    best: DetectedFace
    timecodes: list[float] = field(default_factory=list)


def _cluster(detections: list[tuple[float | None, DetectedFace]], analyzer: FaceAnalyzer) -> list[_Cluster]:
    clusters: list[_Cluster] = []

    for timecode, detected in detections:
        cluster = next(
            (
                item
                for item in clusters
                if analyzer.similarity(item.best.vector, detected.vector) >= analyzer.same_person_score
            ),
            None,
        )
        if cluster is None:
            clusters.append(cluster := _Cluster(best=detected))
        elif detected.score > cluster.best.score:
            cluster.best = detected

        if timecode is not None:
            cluster.timecodes.append(timecode)

    return clusters


async def detect_faces(
    version_id: UUID,
    *,
    asset_repository: AssetRepository,
    version_repository: AssetVersionRepository,
    face_repository: FaceRepository,
    renditions: FileStorage,
    processor: MediaProcessor,
    analyzer: FaceAnalyzer,
    face_index: FaceIndex,
    uow: UnitOfWork,
) -> None:
    """Находит лица версии и сразу узнаёт уже подписанных людей."""

    version = await version_repository.read(version_id)
    asset = await asset_repository.read(version.asset_id) if version else None
    already_done = await face_repository.exists_for_version(version_id)
    await uow.rollback()

    if version is None or asset is None or already_done:
        return

    detections = [
        (frame.timecode, detected)
        for frame in await load_frames(version, renditions=renditions, processor=processor)
        for detected in await analyzer.detect(frame.image)
    ]
    if not detections:
        return

    faces: list[Face] = []
    points: list[FacePoint] = []

    for cluster in _cluster(detections, analyzer):
        face = Face(
            asset_id=asset.id,
            version_id=version.id,
            box=cluster.best.box,
            timecodes=tuple(sorted(cluster.timecodes)),
        )
        known = await face_index.search(
            cluster.best.vector,
            SearchScope(collection_ids=None),
            limit=1,
            min_score=analyzer.same_person_score,
            only_people=True,
        )
        if known and known[0].person_id:
            face.match(known[0].person_id)

        await renditions.upload_bytes(face_thumbnail_key(face.id), cluster.best.thumbnail, "image/webp")
        faces.append(face)
        points.append(
            FacePoint(face_id=face.id, vector=cluster.best.vector, person_id=face.person_id, confirmed=False)
        )

    for face in faces:
        await face_repository.create(face)
    await uow.commit()

    await face_index.replace_version(index_state(asset), version.id, points)


async def propagate_face_assignment(
    face_id: UUID,
    *,
    face_repository: FaceRepository,
    analyzer: FaceAnalyzer,
    face_index: FaceIndex,
    uow: UnitOfWork,
) -> None:
    """Обновляет индекс после подписи лица и узнаёт этого человека на неподписанных лицах."""

    face = await face_repository.read(face_id)
    if face is None:
        return

    await face_index.set_person([face.id], face.person_id, confirmed=face.is_confirmed)

    if face.person_id is None or (vector := await face_index.get_vector(face.id)) is None:
        return

    hits = await face_index.search(
        vector,
        SearchScope(collection_ids=None),
        limit=PROPAGATION_LIMIT,
        min_score=analyzer.same_person_score,
        only_unconfirmed=True,
    )
    matched = []
    for similar in await face_repository.get_by_ids([hit.face_id for hit in hits if hit.face_id != face.id]):
        if similar.match(face.person_id):
            await face_repository.update(similar)
            matched.append(similar.id)

    await uow.commit()
    await face_index.set_person(matched, face.person_id, confirmed=False)

from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.dependencies.auth import CurrentUser
from src.api.dependencies.db import OutboxDep, UnitOfWorkDep
from src.api.dependencies.repositories import (
    AssetRepositoryDep,
    CollectionRepositoryDep,
    FaceRepositoryDep,
    PersonRepositoryDep,
)
from src.api.dependencies.services import FaceIndexDep, MediaUrlsDep
from src.application.people import usecases
from src.application.people.dtos import (
    AssignFaceDTO,
    FaceResponse,
    PersonDTO,
    PersonResponse,
    UpdatePersonDTO,
)

router = APIRouter(tags=["Люди"])


@router.get("/people", summary="Справочник людей", description="Активы с человеком: GET /assets?personId=…")
async def list_people(
    _: CurrentUser,
    people: PersonRepositoryDep,
    faces: FaceRepositoryDep,
    media_urls: MediaUrlsDep,
    query: Annotated[str | None, Query(max_length=100)] = None,
) -> list[PersonResponse]:
    return await usecases.list_people(
        query, person_repository=people, face_repository=faces, media_urls=media_urls
    )


@router.post("/people", status_code=status.HTTP_201_CREATED, summary="Добавить человека")
async def create_person(
    dto: PersonDTO, auth: CurrentUser, people: PersonRepositoryDep, uow: UnitOfWorkDep
) -> PersonResponse:
    return await usecases.create_person(dto, auth, person_repository=people, uow=uow)


@router.get("/people/{person_id}", summary="Человек")
async def get_person(
    person_id: UUID,
    _: CurrentUser,
    people: PersonRepositoryDep,
    faces: FaceRepositoryDep,
    media_urls: MediaUrlsDep,
) -> PersonResponse:
    return await usecases.get_person(
        person_id, person_repository=people, face_repository=faces, media_urls=media_urls
    )


@router.patch("/people/{person_id}", summary="Изменить (автор или администратор)")
async def update_person(
    person_id: UUID,
    dto: UpdatePersonDTO,
    auth: CurrentUser,
    people: PersonRepositoryDep,
    faces: FaceRepositoryDep,
    media_urls: MediaUrlsDep,
    uow: UnitOfWorkDep,
) -> PersonResponse:
    return await usecases.update_person(
        person_id, dto, auth, person_repository=people, face_repository=faces, media_urls=media_urls, uow=uow
    )


@router.delete(
    "/people/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить (автор или администратор)",
    description="Лица человека становятся неподписанными.",
)
async def delete_person(
    person_id: UUID,
    auth: CurrentUser,
    people: PersonRepositoryDep,
    faces: FaceRepositoryDep,
    face_index: FaceIndexDep,
    uow: UnitOfWorkDep,
) -> None:
    await usecases.delete_person(
        person_id, auth, person_repository=people, face_repository=faces, face_index=face_index, uow=uow
    )


@router.put(
    "/faces/{face_id}/person",
    summary="Подписать лицо",
    description="Похожие неподписанные лица на других активах распознаются автоматически в фоне.",
)
async def assign_face(
    face_id: UUID,
    dto: AssignFaceDTO,
    auth: CurrentUser,
    assets: AssetRepositoryDep,
    collections: CollectionRepositoryDep,
    faces: FaceRepositoryDep,
    people: PersonRepositoryDep,
    media_urls: MediaUrlsDep,
    outbox: OutboxDep,
    uow: UnitOfWorkDep,
) -> FaceResponse:
    return await usecases.assign_face(
        face_id,
        dto,
        auth,
        asset_repository=assets,
        collection_repository=collections,
        face_repository=faces,
        person_repository=people,
        media_urls=media_urls,
        outbox=outbox,
        uow=uow,
    )

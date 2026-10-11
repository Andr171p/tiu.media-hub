from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import CollectionAccessDep, CurrentUser, DBSession
from src.modules.collections import AddMemberDTO, MemberResponse, UpdateMemberDTO, members

router = APIRouter(prefix="/collections/{collection_id}/members", tags=["Members"])


@router.get("", summary="Участники коллекции")
async def list_members(db: DBSession, access: CollectionAccessDep) -> list[MemberResponse]:
    return [MemberResponse.model_validate(member) for member in await members.list_members(db, access)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить участника",
    description="Участников добавляют модераторы, модераторов — только владелец.",
)
async def add_member(db: DBSession, access: CollectionAccessDep, dto: AddMemberDTO) -> MemberResponse:
    member = await members.add_member(db, access, dto)
    await db.commit()
    return MemberResponse.model_validate(member)


@router.patch("/{user_id}", summary="Изменить роль участника")
async def update_member(
    db: DBSession,
    access: CollectionAccessDep,
    user_id: UUID,
    dto: UpdateMemberDTO,
) -> MemberResponse:
    member = await members.update_member(db, access, user_id, dto)
    await db.commit()
    return MemberResponse.model_validate(member)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Исключить участника",
    description="Покинуть коллекцию может любой участник.",
)
async def remove_member(db: DBSession, user: CurrentUser, access: CollectionAccessDep, user_id: UUID) -> None:
    await members.remove_member(db, access, user_id, user)
    await db.commit()

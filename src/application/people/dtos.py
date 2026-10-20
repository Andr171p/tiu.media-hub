from typing import Annotated

from datetime import datetime
from uuid import UUID

from pydantic import Field, StringConstraints

from src.application.dtos import CamelModel

type PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PersonDTO(CamelModel):
    name: PersonName
    description: str | None = Field(default=None, max_length=2000, description="Должность, подразделение")


class UpdatePersonDTO(CamelModel):
    name: PersonName | None = None
    description: str | None = Field(default=None, max_length=2000)


class PersonResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    cover_url: str | None = Field(description="Миниатюра подписанного лица")
    created_by: UUID
    created_at: datetime


class BoxDTO(CamelModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class FaceResponse(CamelModel):
    id: UUID
    box: BoxDTO = Field(description="Положение на превью, доли кадра")
    timecodes: list[float] = Field(description="Моменты появления в видео, секунды")
    person_id: UUID | None
    person_name: str | None
    confirmed: bool = Field(description="Подписано вручную; иначе распознано автоматически")
    thumbnail_url: str


class AssignFaceDTO(CamelModel):
    """Укажите существующего человека, имя нового или ``null`` в обоих, чтобы снять подпись."""

    person_id: UUID | None = None
    new_person_name: PersonName | None = None

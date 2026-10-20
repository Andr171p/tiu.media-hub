from typing import Annotated

from datetime import datetime
from uuid import UUID

from pydantic import Field, PositiveInt, StringConstraints

from src.application.dtos import CamelModel
from src.domain.collections import (
    Collection,
    CollectionRole,
    MetadataField,
    MetadataFieldType,
    Permission,
    UploadPolicy,
    Visibility,
)
from src.domain.collections.models import DEFAULT_ALLOWED_TYPES, DEFAULT_MAX_FILE_SIZE

type Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
type MimePattern = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[\w.+-]+/(\*|[\w.+-]+)$")
]


class UploadPolicyDTO(CamelModel):
    allowed_types: list[MimePattern] = Field(
        default_factory=lambda: sorted(DEFAULT_ALLOWED_TYPES),
        min_length=1,
        description="MIME-маски разрешённых файлов",
        examples=[["image/*", "video/*"]],
    )
    max_file_size: PositiveInt = Field(default=DEFAULT_MAX_FILE_SIZE, description="Максимальный размер, байт")

    def to_domain(self) -> UploadPolicy:
        return UploadPolicy(allowed_types=frozenset(self.allowed_types), max_file_size=self.max_file_size)


class MetadataFieldDTO(CamelModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$", examples=["event_date"])
    label: Name = Field(examples=["Дата мероприятия"])
    type: MetadataFieldType
    required: bool = False
    options: list[Name] = Field(default_factory=list, description="Варианты для типа choice")
    multiple: bool = Field(default=False, description="Несколько значений (только choice)")

    def to_domain(self) -> MetadataField:
        return MetadataField(
            key=self.key,
            label=self.label,
            type=self.type,
            required=self.required,
            options=tuple(self.options),
            multiple=self.multiple,
        )


class CreateCollectionDTO(CamelModel):
    name: Name
    description: str | None = Field(default=None, max_length=5000)
    visibility: Visibility = Visibility.PRIVATE
    upload_policy: UploadPolicyDTO = Field(default_factory=UploadPolicyDTO)
    metadata_schema: list[MetadataFieldDTO] = Field(default_factory=list, max_length=50)


class UpdateCollectionDTO(CamelModel):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=5000)
    visibility: Visibility | None = None
    upload_policy: UploadPolicyDTO | None = None
    metadata_schema: list[MetadataFieldDTO] | None = Field(default=None, max_length=50)


class CollectionResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    visibility: Visibility
    upload_policy: UploadPolicyDTO
    metadata_schema: list[MetadataFieldDTO]
    created_at: datetime
    updated_at: datetime

    role: CollectionRole | None = Field(
        description="Роль текущего пользователя (None — владелец или не участник)"
    )
    permissions: list[Permission] = Field(description="Что может текущий пользователь")
    asset_count: int | None = Field(default=None, description="Активов в коллекции (без корзины)")

    @classmethod
    def build(
        cls,
        collection: Collection,
        *,
        role: CollectionRole | None,
        permissions: frozenset[Permission],
        asset_count: int | None = None,
    ) -> CollectionResponse:
        return cls(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            owner_id=collection.owner_id,
            visibility=collection.visibility,
            upload_policy=UploadPolicyDTO(
                allowed_types=sorted(collection.upload_policy.allowed_types),
                max_file_size=collection.upload_policy.max_file_size,
            ),
            metadata_schema=[MetadataFieldDTO.model_validate(item) for item in collection.metadata_schema],
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            role=role,
            permissions=sorted(permissions),
            asset_count=asset_count,
        )


class MemberDTO(CamelModel):
    user_id: UUID
    role: CollectionRole


class MemberResponse(MemberDTO):
    display_name: str | None = Field(default=None, description="Имя, если пользователь уже входил в систему")
    email: str | None = None

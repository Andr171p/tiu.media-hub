from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database.base import Base
from src.core.database.types import DatetimeTz, StrNull, StrUnique, UuidNull


class UploadStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class UploadSession(Base):
    """Сессия прямой загрузки файла в S3."""

    __tablename__ = "upload_sessions"

    storage_key: Mapped[StrUnique]
    filename: Mapped[str]
    content_type: Mapped[StrNull]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    uploaded_by: Mapped[UuidNull]
    status: Mapped[UploadStatus] = mapped_column(default=UploadStatus.PENDING)
    expires_at: Mapped[DatetimeTz]
    object_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stored_objects.id", ondelete="RESTRICT"),
        nullable=True,
    )

    object: Mapped[StoredObject | None] = relationship()


class StoredObject(Base):
    """
    Физически загруженный объект в хранилище.
    Если такой объект существует, то файл гарантировано загружен в S3,
    его размер и checksum подтверждены.
    """

    __tablename__ = "stored_objects"

    storage_key: Mapped[StrUnique]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    content_type: Mapped[StrNull]

    __table_args__ = (
        UniqueConstraint("sha256", "size_bytes", name="uq_stored_object_sha256_size"),
    )


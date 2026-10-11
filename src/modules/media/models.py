from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.core.database.types import DatetimeTz, DatetimeTzNull, StrNull, StrUnique


class UploadStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"


class StoredObject(Base):
    """
    Файл в хранилище, содержимое которого подтверждено: размер и SHA-256 сверены с S3.
    Объекты адресуются содержимым: одинаковый файл хранится один раз.
    """

    __tablename__ = "stored_objects"

    storage_key: Mapped[StrUnique]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str]
    content_type: Mapped[str] = mapped_column(comment="Заявленный при загрузке MIME-тип")

    verified_at: Mapped[DatetimeTzNull] = mapped_column(comment="Последняя успешная проверка целостности")
    integrity_error: Mapped[StrNull] = mapped_column(comment="Результат последней неуспешной проверки")

    __table_args__ = (
        UniqueConstraint("sha256", "size_bytes"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
    )


class UploadSession(Base):
    """Прямая загрузка файла в S3 по presigned URL."""

    __tablename__ = "upload_sessions"

    storage_key: Mapped[StrUnique]
    filename: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str]
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[UploadStatus] = mapped_column(default=UploadStatus.PENDING, index=True)
    expires_at: Mapped[DatetimeTz]

    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("stored_objects.id", ondelete="RESTRICT"))
    object: Mapped[StoredObject | None] = relationship(lazy="raise")


__all__ = ["StoredObject", "UploadSession", "UploadStatus"]

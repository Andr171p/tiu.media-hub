from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Предсказуемые имена ограничений: Alembic сможет их удалять и переименовывать
_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)

    # Серверные значения (created_at, updated_at) возвращаются через RETURNING сразу после flush
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    # StrEnum хранится строкой значения: новые варианты не требуют ALTER TYPE
    type_annotation_map = {  # noqa: RUF012
        StrEnum: Enum(
            StrEnum,
            native_enum=False,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
    }

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """Сущности, которые не удаляются физически: история и ссылки остаются целыми."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["Base", "SoftDeleteMixin"]

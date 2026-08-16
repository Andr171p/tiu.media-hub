from typing import Any

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Base

type CreateWrapper[
    ModelT: Base, CreateDTO: BaseModel, CreateOptionsT,
] = Callable[
    [
        Callable[[dict[str, Any] | None], Awaitable[ModelT]],
        CreateDTO,
        CreateOptionsT | None,
    ],
    Awaitable[ModelT],
]

type ReadWrapper[ModelT: Base, ReadOptionsT] = Callable[
    [
        Callable[[], Awaitable[ModelT | None]],
        Any,
        ReadOptionsT | None,
    ],
    Awaitable[ModelT | None],
]

type UpdateWrapper[
    ModelT: Base, UpdateDTO: BaseModel, UpdateOptionsT,
] = Callable[
    [
        Callable[[dict[str, Any] | None], Awaitable[ModelT]],
        ModelT,
        UpdateDTO,
        UpdateOptionsT | None,
    ],
    Awaitable[ModelT],
]

type DeleteWrapper[ModelT: Base, DeleteOptionsT] = Callable[
    [
        Callable[[], Awaitable[None]],
        ModelT,
        DeleteOptionsT | None,
    ],
    Awaitable[None],
]


class Crud[
    ModelT: Base,
    CreateDTO: BaseModel,
    UpdateDTO: BaseModel,
    CreateOptionsT,
    ReadOptionsT,
    UpdateOptionsT,
    DeleteOptionsT,
]:
    def __init__(
            self,
            model: type[ModelT],
            *,
            create_wrapper: CreateWrapper[ModelT, CreateDTO, CreateOptionsT] | None = None,
            read_wrapper: ReadWrapper[ModelT, ReadOptionsT] | None = None,
            update_wrapper: UpdateWrapper[ModelT, UpdateDTO, UpdateOptionsT] | None = None,
            delete_wrapper: DeleteWrapper[ModelT, DeleteOptionsT] | None = None,
    ) -> None:
        self._model = model

        self._create_wrapper = create_wrapper
        self._read_wrapper = read_wrapper
        self._update_wrapper = update_wrapper
        self._delete_wrapper = delete_wrapper

    async def create(
            self, session: AsyncSession, dto: CreateDTO, options: CreateOptionsT | None = None,
    ) -> ModelT:

        async def _base_create(kwargs: dict[str, Any] | None = None) -> ModelT:
            values = {**dto.model_dump(), **(kwargs or {})}
            model = self._model(**values)

            session.add(model)
            await session.flush()

            return model

        if self._create_wrapper:
            return await self._create_wrapper(_base_create, dto, options)

        return await _base_create()

    async def read(
            self,
            session: AsyncSession,
            uid: UUID,
            options: ReadOptionsT | None = None,
    ) -> ModelT | None:

        async def _base_read() -> ModelT | None:
            stmt = select(self._model).where(self._model.id == uid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        if self._read_wrapper:
            return await self._read_wrapper(_base_read, uid, options)

        return await _base_read()

    async def update(
            self,
            session: AsyncSession,
            model: ModelT,
            dto: UpdateDTO,
            options: UpdateOptionsT | None = None,
    ) -> ModelT:

        async def _base_update(kwargs: dict[str, Any] | None = None) -> ModelT:
            values = {**dto.model_dump(exclude_none=True), **(kwargs or {})}

            for field, value in values.items():
                setattr(model, field, value)

            await session.flush()
            return model

        if self._update_wrapper:
            return await self._update_wrapper(_base_update, model, dto, options)

        return await _base_update()

    async def delete(
            self, session: AsyncSession, model: ModelT, options: DeleteOptionsT | None = None,
    ) -> None:

        async def _base_delete() -> None:
            model.deleted_at = datetime.now(UTC)
            await session.flush()

        if self._delete_wrapper:
            await self._delete_wrapper(_base_delete(), model, options)
            return

        await _base_delete()

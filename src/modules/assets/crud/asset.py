from typing import Any

from collections.abc import Awaitable, Callable

from src.core.assets.models import Asset
from src.core.assets.schemas import CreateAssetDTO, UpdateAssetDTO
from src.core.auth.models import User
from src.core.common.crud import Crud


async def create_wrapper(
        func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
        dto: CreateAssetDTO,
        user: User | None = None,
) -> Asset:

    if user is None:
        raise ValueError(...)

    return await func({"author_id": ...})


crud = Crud[
    Asset,
    CreateAssetDTO,
    UpdateAssetDTO,
    User, None, None, None,
](Asset, create_wrapper=create_wrapper)

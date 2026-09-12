from typing import Any

from collections.abc import Awaitable, Callable

from src.core.assets.models import Asset
from src.core.assets.dtos import CreateAssetDTO, UpdateAssetDTO
from src.core.auth.models import User
from src.core.auth.policies import check_roles
from src.core.common.crud import Crud


async def create_wrapper(
    func: Callable[[dict[str, Any] | None], Awaitable[Asset]],
    _dto: CreateAssetDTO,
    user: User | None = None,
) -> Asset:

    if user is None:
        raise ValueError("Creating an asset requires an authenticated user.")

    check_roles(user, frozenset({"user", "admin"}), all_required=False)
    return await func({
        "author_id": user.id,
        "descriptive_metadata": _dto.descriptive_metadata.model_dump(mode="json"),
    })


crud = Crud[
    Asset,
    CreateAssetDTO,
    UpdateAssetDTO,
    User,
    None,
    None,
    None,
](Asset, create_wrapper=create_wrapper)

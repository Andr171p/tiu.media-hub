from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.assets.models import AssetVersion


async def get_next_asset_version_number(session: AsyncSession, asset_id: UUID) -> int:
    """Получает номер следующей версии."""

    stmt = (
        select(func.coalesce(func.max(AssetVersion.number), 0))
        .where(AssetVersion.asset_id == asset_id)
    )
    return await session.scalar(stmt) + 1

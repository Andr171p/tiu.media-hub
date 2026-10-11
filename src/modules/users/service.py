from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import Auth

from .models import User


async def sync_profile(session: AsyncSession, profile: Auth.User) -> User:
    """Создаёт или обновляет локальный профиль по данным токена."""

    values = {
        "email": profile.email,
        "username": profile.username,
        "full_name": profile.full_name,
        "last_seen_at": func.now(),
    }
    stmt = (
        insert(User)
        .values(id=profile.id, **values)
        .on_conflict_do_update(index_elements=[User.id], set_=values)
        .returning(User)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


async def search_users(session: AsyncSession, query: str, *, limit: int = 20) -> Sequence[User]:
    pattern = f"%{_escape_like(query.strip())}%"
    stmt = (
        select(User)
        .where(
            or_(
                User.email.ilike(pattern),
                User.username.ilike(pattern),
                User.full_name.ilike(pattern),
            ),
        )
        .order_by(User.full_name, User.email)
        .limit(limit)
    )
    return (await session.scalars(stmt)).all()


__all__ = ["search_users", "sync_profile"]

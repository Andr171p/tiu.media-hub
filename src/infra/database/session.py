from ddf.infra.database.sqlalchemy import PostgresConfig
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_engine(config: PostgresConfig) -> AsyncEngine:
    return create_async_engine(
        config.uri,
        pool_size=config.pool_resize,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_pre_ping=True,
        echo=config.echo,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


__all__ = ["create_engine", "create_session_factory"]

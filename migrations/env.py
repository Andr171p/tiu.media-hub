import asyncio
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

from src.core.database import Base, PostgresConfig  # noqa: E402
from src.core.database.types import PydanticJSONB  # noqa: E402
from src.modules import assets, collections, media, tags, users  # noqa: E402, F401 — регистрация моделей

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Миграции не зависят от кода приложения: типизированный JSONB в схеме — обычный JSONB."""

    if type_ == "type" and isinstance(obj, PydanticJSONB):
        autogen_context.imports.add("from sqlalchemy.dialects import postgresql")  # type: ignore[attr-defined]
        return "postgresql.JSONB(astext_type=sa.Text())"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=PostgresConfig().uri.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(PostgresConfig().uri, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())

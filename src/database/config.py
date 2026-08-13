from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "12345"
    db: str = "media-hub"

    driver: Literal["asyncpg"] = "asyncpg"

    @property
    def uri(self) -> str:
        return ...

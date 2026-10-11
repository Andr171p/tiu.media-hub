from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: PositiveInt = 5432
    username: str = "dam"
    password: SecretStr = SecretStr("dam")
    db: str = "dam"

    pool_size: PositiveInt = Field(default=10, description="Постоянные соединения пула")
    max_overflow: int = Field(default=10, ge=0, description="Дополнительные соединения сверх пула")
    echo: bool = Field(default=False, description="Логировать SQL")

    @property
    def uri(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.username,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.db,
        )

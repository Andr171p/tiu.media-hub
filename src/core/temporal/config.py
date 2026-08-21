from pydantic_settings import BaseSettings, SettingsConfigDict


class TemporalConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEMPORAL_")

    host: str = "localhost"
    port: int = 7233
    namespace: str = "default"

    task_queue: str = "default"

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

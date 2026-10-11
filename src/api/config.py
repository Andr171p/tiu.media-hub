from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_")

    title: str = "TIU Media Hub"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="Origins фронтенда. CORS не заменяет авторизацию",
    )

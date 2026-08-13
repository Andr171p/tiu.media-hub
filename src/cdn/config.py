from pydantic_settings import BaseSettings, SettingsConfigDict


class CdnConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CDN_")

    base_url: str = "http://localhost:80"
    path_prefix: str = "/public"

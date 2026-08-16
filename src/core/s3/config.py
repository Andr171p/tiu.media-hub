from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="S3_")

    service_name: str = "s3"
    access_key: str = ""
    secret_key: str = ""
    endpoint_url: str = "http://localhost:9000"
    bucket: str = ""

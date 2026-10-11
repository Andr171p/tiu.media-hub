from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UPLOAD_")

    url_expires_in: PositiveInt = Field(default=60 * 60, description="Время жизни ссылки загрузки, секунд")
    max_file_size: PositiveInt = Field(
        default=1024 * 1024 * 1024,
        description="Глобальный предел размера файла, байт (коллекция может ограничить сильнее)",
    )
    download_url_expires_in: PositiveInt = Field(
        default=10 * 60,
        description="Время жизни ссылки на скачивание оригинала, секунд",
    )

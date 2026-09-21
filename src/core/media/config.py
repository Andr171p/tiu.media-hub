from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_UPLOAD_URL_EXPIRES_IN = 60 * 60
_DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


class UploadConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UPLOAD_")

    url_expires_in: PositiveInt = Field(
        default=_DEFAULT_UPLOAD_URL_EXPIRES_IN,
        description="Время жизни сессии загрузки файла",
    )
    max_file_size: PositiveInt = Field(
        default=_DEFAULT_MAX_FILE_SIZE,
        description="Максимальный размер загружаемого файла",
    )

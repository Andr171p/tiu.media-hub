from urllib.parse import quote

from pydantic import Field, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBIT_")

    host: str = Field(default="localhost", description="Хост RabbitMQ")
    port: PositiveInt = Field(default=5672, description="AMQP порт")
    username: str = Field(default="dam", description="Пользователь")
    password: SecretStr = Field(default=SecretStr("dam"), description="Пароль")
    virtualhost: str = Field(default="/", description="Virtual host")

    @property
    def url(self) -> str:
        credentials = f"{quote(self.username)}:{quote(self.password.get_secret_value())}"
        return f"amqp://{credentials}@{self.host}:{self.port}/{quote(self.virtualhost, safe='')}"

"""
Очереди задач (RabbitMQ):

* ``media`` — CPU: превью, прокси-видео, рендер редактора, обслуживание;
* ``ai`` — модели: CLIP, лица, описание и теги, расшифровка речи, синхронизация индекса.

Разделение не даёт долгому перекодированию видео задерживать поиск и наоборот.
"""

from urllib.parse import quote

from pydantic import PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from taskiq.middlewares import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.queue import Queue


class RabbitConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBIT_")

    host: str = "localhost"
    port: PositiveInt = 5672
    username: str = "dam"
    password: SecretStr = SecretStr("dam")
    virtualhost: str = "/"

    @property
    def url(self) -> str:
        credentials = f"{quote(self.username)}:{quote(self.password.get_secret_value())}"
        return f"amqp://{credentials}@{self.host}:{self.port}/{quote(self.virtualhost, safe='')}"


def _create_broker(queue: str) -> AioPikaBroker:
    """Своя очередь, очередь отложенных повторов и dead letter для каждого типа воркеров."""

    return AioPikaBroker(
        RabbitConfig().url,
        task_queues=[Queue(name=queue)],
        delay_queue=Queue(name=f"{queue}.delay"),
        dead_letter_queue=Queue(name=f"{queue}.dead_letter"),
    ).with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=3,
            default_delay=10,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=600,
        )
    )


media_broker = _create_broker("dam.media")
ai_broker = _create_broker("dam.ai")

__all__ = ["RabbitConfig", "ai_broker", "media_broker"]

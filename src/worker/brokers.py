"""
Два брокера — две независимые очереди, которые масштабируются отдельно:

* ``processing`` — CPU-работа: проверка целостности, метаданные, производные, водяные знаки;
* ``indexing`` — эмбеддинги (Infinity) и индекс поиска (Qdrant), в основном ожидание сети.

У каждого брокера свой exchange, очередь, очередь отложенных повторов и dead-letter.
"""

from dotenv import load_dotenv
from taskiq.middlewares import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue, QueueType

from src.core.broker import RabbitConfig

load_dotenv()


def _create_broker(name: str, *, prefetch: int) -> AioPikaBroker:
    prefix = f"dam.{name}"
    broker = AioPikaBroker(
        RabbitConfig().url,
        qos=prefetch,
        exchange=Exchange(name=prefix),
        task_queues=[Queue(name=prefix)],
        # Отложенные повторы: сообщение ждёт в delay-очереди и по TTL возвращается в основную
        delay_queue=Queue(name=f"{prefix}.delay", type=QueueType.CLASSIC),
        dead_letter_queue=Queue(name=f"{prefix}.dead_letter"),
    )
    return broker.with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=3,
            default_delay=10,
            use_jitter=True,
            use_delay_exponent=True,
            max_delay_exponent=300,
        ),
    )


processing_broker = _create_broker("processing", prefetch=4)
indexing_broker = _create_broker("indexing", prefetch=16)

__all__ = ["indexing_broker", "processing_broker"]

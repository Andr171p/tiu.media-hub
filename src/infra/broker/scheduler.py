"""
Периодические задачи. Запуск строго в одном экземпляре:
``taskiq scheduler src.infra.broker.scheduler:scheduler``.
"""

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from .media_tasks import media_broker

scheduler = TaskiqScheduler(broker=media_broker, sources=[LabelScheduleSource(media_broker)])

__all__ = ["scheduler"]

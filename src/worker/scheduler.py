"""
Планировщик периодических задач (метка ``schedule`` у задачи). Запуск — строго в одном экземпляре:

    taskiq scheduler src.worker.scheduler:scheduler
"""

from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from .processing import broker

scheduler = TaskiqScheduler(broker, sources=[LabelScheduleSource(broker)])

__all__ = ["scheduler"]

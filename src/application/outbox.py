from ddf.application.events import serialize_event
from ddf.application.outbox import OutboxMessage, OutboxStore
from ddf.domain.models import Entity


async def save_events_to_outbox(outbox: OutboxStore, *entities: Entity) -> None:
    """Переносит накопленные доменные события в outbox текущей транзакции (доставка — relay)."""

    messages = [
        OutboxMessage(type=event.event_type, occurred_on=event.occurred_on, payload=serialize_event(event))
        for entity in entities
        for event in entity.collect_events()
    ]
    await outbox.save_all(messages)


__all__ = ["save_events_to_outbox"]

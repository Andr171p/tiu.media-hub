from uuid import UUID

from .ports import Transcript


class TranscriptRepository:
    async def save(self, version_id: UUID, transcript: Transcript) -> None:
        """Создаёт или заменяет расшифровку версии."""
        raise NotImplementedError

    async def get(self, version_id: UUID) -> Transcript | None:
        raise NotImplementedError


__all__ = ["TranscriptRepository"]

from typing import Protocol

from collections.abc import Sequence
from uuid import UUID

from ddf.application.repositories import Repository

from src.domain.portals import Portal


class PortalRepository(Repository[Portal]):
    async def find_by_slug(self, slug: str) -> Portal | None:
        raise NotImplementedError

    async def list_owned(self, owner_id: UUID | None) -> Sequence[Portal]:
        """Порталы владельца; ``None`` — все (администратор)."""
        raise NotImplementedError


class PortalSecrets(Protocol):
    """Пароли порталов и токены доступа посетителей, вошедших по паролю."""

    def hash_password(self, password: str) -> str: ...

    def verify_password(self, password: str, password_hash: str) -> bool: ...

    def issue_token(self, portal_id: UUID, *, ttl: int) -> str: ...

    def verify_token(self, token: str, portal_id: UUID) -> bool: ...


__all__ = ["PortalRepository", "PortalSecrets"]

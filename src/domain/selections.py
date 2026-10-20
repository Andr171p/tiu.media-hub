from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from ddf.domain.exceptions import InvariantViolationError
from ddf.domain.models import AggregateRoot

MAX_SELECTION_SIZE = 1000


@dataclass(kw_only=True)
class Selection(AggregateRoot):
    """Подборка: упорядоченный список активов из разных коллекций."""

    name: str
    description: str | None = None
    owner_id: UUID
    shared: bool = False
    """Видна всем сотрудникам (активы — только из доступных им коллекций)."""

    asset_ids: list[UUID] = field(default_factory=list)

    def add(self, asset_ids: Iterable[UUID]) -> None:
        new_ids = [asset_id for asset_id in dict.fromkeys(asset_ids) if asset_id not in self.asset_ids]

        if len(self.asset_ids) + len(new_ids) > MAX_SELECTION_SIZE:
            raise InvariantViolationError(f"Selection cannot contain more than {MAX_SELECTION_SIZE} assets.")

        self.asset_ids.extend(new_ids)
        self.updated_at = datetime.now(UTC)

    def remove(self, asset_ids: Iterable[UUID]) -> None:
        removed = set(asset_ids)
        self.asset_ids = [asset_id for asset_id in self.asset_ids if asset_id not in removed]
        self.updated_at = datetime.now(UTC)

    def reorder(self, asset_ids: list[UUID]) -> None:
        if sorted(asset_ids) != sorted(self.asset_ids):
            raise InvariantViolationError("New order must contain exactly the same assets.")

        self.asset_ids = list(asset_ids)
        self.updated_at = datetime.now(UTC)

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from ddf.domain.exceptions import InvariantViolationError

EXPIRING_WITHIN = timedelta(days=30)


class LicenseType(StrEnum):
    OWN = "own"
    """Собственный контент организации."""

    ROYALTY_FREE = "royalty_free"
    RIGHTS_MANAGED = "rights_managed"
    CREATIVE_COMMONS = "creative_commons"
    EDITORIAL = "editorial"
    """Только редакционное использование: новости, пресса."""

    PUBLIC_DOMAIN = "public_domain"


class UsageChannel(StrEnum):
    PRINT = "print"
    DIGITAL = "digital"
    SOCIAL = "social"
    OUTDOOR = "outdoor"
    TV = "tv"
    PRESS = "press"


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    NOT_STARTED = "not_started"


@dataclass(frozen=True, kw_only=True)
class Period:
    """Срок действия: любая из границ может быть открытой."""

    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        if self.start and self.end and self.start > self.end:
            raise InvariantViolationError("Period start must not be after its end.")


@dataclass(frozen=True, kw_only=True)
class License:
    """Права на использование актива. Пустые ``territories``/``channels`` означают «без ограничений»."""

    type: LicenseType
    holder: str | None = None
    period: Period = Period()
    territories: frozenset[str] = frozenset()
    channels: frozenset[UsageChannel] = frozenset()
    restrictions: str | None = None

    def status(self, today: date) -> LicenseStatus:
        if self.period.start and today < self.period.start:
            return LicenseStatus.NOT_STARTED

        if self.period.end is None:
            return LicenseStatus.ACTIVE

        if today > self.period.end:
            return LicenseStatus.EXPIRED

        if self.period.end - today <= EXPIRING_WITHIN:
            return LicenseStatus.EXPIRING

        return LicenseStatus.ACTIVE

    def is_usable(self, today: date) -> bool:
        return self.status(today) in {LicenseStatus.ACTIVE, LicenseStatus.EXPIRING}

"""
Проверка метаданных и лицензии. Чистые функции: результат зависит от текущей даты и схемы коллекции,
поэтому вычисляется при чтении, а не хранится. В версии хранятся только замечания обработки файла.
"""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from enum import StrEnum

from pydantic import Field, JsonValue

from src.core.common.schemas import Schema
from src.modules.collections import missing_required_fields
from src.modules.collections.settings import LicensePolicy, MetadataField

from .licensing import License
from .meta import EmbeddedMetadata, VersionMeta

_EXPIRY_WARNING_PERIOD = timedelta(days=30)


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueCode(StrEnum):
    LICENSE_MISSING = "license_missing"
    LICENSE_EXPIRED = "license_expired"
    LICENSE_EXPIRING = "license_expiring"
    REQUIRED_METADATA_MISSING = "required_metadata_missing"
    RIGHTS_HOLDER_MISMATCH = "rights_holder_mismatch"
    EMBEDDED_RIGHTS_UNDECLARED = "embedded_rights_undeclared"
    CONTENT_TYPE_MISMATCH = "content_type_mismatch"
    LOCATION_EMBEDDED = "location_embedded"


class Issue(Schema):
    code: IssueCode
    severity: IssueSeverity
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


def _license_issues(license_: License | None, policy: LicensePolicy, today: date) -> list[Issue]:
    if license_ is None:
        return [
            Issue(
                code=IssueCode.LICENSE_MISSING,
                severity=IssueSeverity.ERROR if policy.required else IssueSeverity.WARNING,
                message="Лицензия не указана.",
            ),
        ]

    if license_.valid_until is None:
        return []

    details: dict[str, JsonValue] = {"validUntil": license_.valid_until.isoformat()}
    if license_.valid_until < today:
        return [
            Issue(
                code=IssueCode.LICENSE_EXPIRED,
                severity=IssueSeverity.ERROR,
                message="Срок прав истёк.",
                details=details,
            )
        ]
    if license_.valid_until - today <= _EXPIRY_WARNING_PERIOD:
        return [
            Issue(
                code=IssueCode.LICENSE_EXPIRING,
                severity=IssueSeverity.WARNING,
                message="Срок прав скоро истекает.",
                details=details,
            ),
        ]
    return []


def _embedded_rights_issues(license_: License | None, embedded: EmbeddedMetadata) -> list[Issue]:
    declared_in_file = embedded.copyright or embedded.creator
    if not declared_in_file:
        return []

    if license_ is None:
        return [
            Issue(
                code=IssueCode.EMBEDDED_RIGHTS_UNDECLARED,
                severity=IssueSeverity.WARNING,
                message=f"В файле указан автор или правообладатель «{declared_in_file}», а лицензии нет.",
                details={"embedded": declared_in_file},
            ),
        ]

    if (
        license_.holder
        and embedded.copyright
        and license_.holder.casefold() not in embedded.copyright.casefold()
    ):
        return [
            Issue(
                code=IssueCode.RIGHTS_HOLDER_MISMATCH,
                severity=IssueSeverity.WARNING,
                message="Правообладатель в файле отличается от указанного в лицензии.",
                details={"embedded": embedded.copyright, "declared": license_.holder},
            ),
        ]
    return []


def evaluate_compliance(
    *,
    license_: License | None,
    custom_meta: Mapping[str, JsonValue],
    fields: Sequence[MetadataField],
    license_policy: LicensePolicy,
    meta: VersionMeta | None,
    today: date,
) -> list[Issue]:
    issues = _license_issues(license_, license_policy, today)

    if missing := missing_required_fields(fields, custom_meta):
        issues.append(
            Issue(
                code=IssueCode.REQUIRED_METADATA_MISSING,
                severity=IssueSeverity.ERROR,
                message="Не заполнены обязательные поля метаданных.",
                details={"fields": list(missing)},
            ),
        )

    if (embedded := getattr(meta, "embedded", None)) is not None:
        issues.extend(_embedded_rights_issues(license_, embedded))
        if embedded.has_location:
            issues.append(
                Issue(
                    code=IssueCode.LOCATION_EMBEDDED,
                    severity=IssueSeverity.INFO,
                    message="Оригинал содержит GPS-координаты. Из превью они удалены.",
                ),
            )

    return issues


__all__ = ["Issue", "IssueCode", "IssueSeverity", "evaluate_compliance"]

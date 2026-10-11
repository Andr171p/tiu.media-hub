from typing import Annotated, Self

from datetime import date
from enum import StrEnum

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from src.core.common.schemas import Schema

type RightsText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class LicenseType(StrEnum):
    ALL_RIGHTS_RESERVED = "all-rights-reserved"
    CC0 = "cc0"
    CC_BY = "cc-by"
    CC_BY_SA = "cc-by-sa"
    CC_BY_ND = "cc-by-nd"
    CC_BY_NC = "cc-by-nc"
    CC_BY_NC_SA = "cc-by-nc-sa"
    CC_BY_NC_ND = "cc-by-nc-nd"
    PUBLIC_DOMAIN = "public-domain"
    CUSTOM = "custom"


class License(Schema):
    """Права на использование актива: кто владеет и на каких условиях можно использовать."""

    type: LicenseType
    holder: RightsText | None = Field(default=None, description="Правообладатель", examples=["ФГБОУ ВО ТИУ"])
    author: RightsText | None = Field(default=None, description="Автор произведения")
    source_url: HttpUrl | None = Field(default=None, description="Источник или текст лицензии")
    terms: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None = Field(
        default=None,
        description="Условия использования (обязательны для custom)",
    )
    valid_until: date | None = Field(default=None, description="Дата окончания прав")

    @model_validator(mode="after")
    def _check_terms(self) -> Self:
        if self.type is LicenseType.CUSTOM and not self.terms:
            raise ValueError("Custom license requires terms.")
        return self


__all__ = ["License", "LicenseType"]

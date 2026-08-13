from typing import Annotated

from sqlalchemy import TEXT
from sqlalchemy.orm import mapped_column

type IntNull = Annotated[int | None, mapped_column(nullable=True)]
type FloatNull = Annotated[float | None, mapped_column(nullable=True)]
type TextNull = Annotated[str | None, mapped_column(TEXT, nullable=True)]
type StrUnique = Annotated[str, mapped_column(unique=True)]

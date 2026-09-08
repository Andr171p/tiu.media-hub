from typing import Annotated

from pydantic import Field

type Str255 = Annotated[str, Field(min_length=1, max_length=255)]

__all__ = ["Str255"]

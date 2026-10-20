from dataclasses import dataclass

from ddf.domain.exceptions import InvariantViolationError


@dataclass(frozen=True, kw_only=True)
class Box:
    """Прямоугольник в долях от ширины и высоты кадра: не зависит от разрешения файла."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not (0 <= self.x < 1 and 0 <= self.y < 1 and 0 < self.width <= 1 and 0 < self.height <= 1):
            raise InvariantViolationError("Box must be within the frame.")

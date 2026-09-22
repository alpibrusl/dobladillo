"""Declared interfaces between bricks. See `ports`."""

from dobladillo.interfaces.ports import (
    KINDS,
    Bond,
    Brick,
    Crosstalk,
    Kind,
    Polarity,
    Port,
    can_mate,
    crosstalk,
    unsatisfied,
)

__all__ = [
    "KINDS",
    "Bond",
    "Brick",
    "Crosstalk",
    "Kind",
    "Polarity",
    "Port",
    "can_mate",
    "crosstalk",
    "unsatisfied",
]

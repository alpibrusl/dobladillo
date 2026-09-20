"""Sorting particles, and reporting a fraction honestly.

The readout of the twist-pair experiment is a fraction: what proportion of
objects lie flat as a clean rectangle. So this module's job is not really
classification, it is producing a number with an interval attached, because a
fraction without one cannot be compared with another fraction.

Three classes, and the boundaries are stated rather than tuned:

- **aggregate**: taller than a single layer can be. A sheet is one helix thick;
  anything substantially taller is more than one object.
- **well formed**: the expected dimensions, within tolerance.
- **malformed**: the right height, so a single layer, but the wrong shape.
  This is where a twisted sheet lands when the surface has partly flattened it:
  still one layer, no longer a rectangle.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladilo.imaging.particles import Particle

#: Above this multiple of the expected single-layer height, a particle is more
#: than one object.
AGGREGATE_HEIGHT_FACTOR = 1.6

#: Fractional tolerance on each dimension for "well formed".
SHAPE_TOLERANCE = 0.20

#: z for a 95% interval.
Z95 = 1.959964


@dataclass(frozen=True)
class Fraction:
    """A proportion with the interval its count actually supports."""

    count: int
    total: int

    @property
    def value(self) -> float:
        return self.count / self.total if self.total else 0.0

    @property
    def ci95(self) -> tuple[float, float]:
        """Wilson interval, not the textbook normal approximation.

        The normal one misbehaves exactly where this measurement lives: near 0
        or 1, and at small counts, it produces intervals that run past the ends
        of the scale. A yield of 100% out of 40 particles is not 100% +- 0%.
        """
        if not self.total:
            return (0.0, 0.0)
        n, p, z = self.total, self.value, Z95
        denominator = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denominator
        spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
        return (max(0.0, centre - spread), min(1.0, centre + spread))

    def as_dict(self) -> dict[str, Any]:
        low, high = self.ci95
        return {
            "count": self.count,
            "total": self.total,
            "fraction": round(self.value, 4),
            "ci95": [round(low, 4), round(high, 4)],
            "plus_minus": round((high - low) / 2, 4),
        }


@dataclass(frozen=True)
class Population:
    counts: dict[str, int]
    total: int
    well_formed: Fraction
    excluded_at_edge: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "counted": self.total,
            "excluded_touching_edge": self.excluded_at_edge,
            "classes": self.counts,
            "well_formed": self.well_formed.as_dict(),
        }


def classify(
    particle: Particle,
    *,
    length_nm: float,
    width_nm: float,
    height_nm: float,
    tolerance: float = SHAPE_TOLERANCE,
) -> str:
    if particle.height_nm > AGGREGATE_HEIGHT_FACTOR * height_nm:
        return "aggregate"
    matches = (
        abs(particle.length_nm - length_nm) <= tolerance * length_nm
        and abs(particle.width_nm - width_nm) <= tolerance * width_nm
    )
    return "well_formed" if matches else "malformed"


def population(
    particles: Sequence[Particle],
    *,
    length_nm: float,
    width_nm: float,
    height_nm: float,
    tolerance: float = SHAPE_TOLERANCE,
) -> Population:
    """Classify everything and report the yield with its interval.

    Particles touching the frame edge are excluded and counted separately: a
    rectangle half outside the scan measures short, and silently including it
    would bias both the dimensions and the fraction.
    """
    inside = [p for p in particles if not p.touches_edge]
    labels = [
        classify(
            p, length_nm=length_nm, width_nm=width_nm, height_nm=height_nm, tolerance=tolerance
        )
        for p in inside
    ]
    counts = Counter(labels)
    return Population(
        counts={k: counts.get(k, 0) for k in ("well_formed", "malformed", "aggregate")},
        total=len(inside),
        well_formed=Fraction(counts.get("well_formed", 0), len(inside)),
        excluded_at_edge=len(particles) - len(inside),
    )

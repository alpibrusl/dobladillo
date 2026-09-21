"""The folding protocol sheet, generated from the defaults in constants.py.

Everything here is a starting point, not a result. The Mg2+ concentration in
particular is screened rather than chosen: origami folding is sharply
Mg-dependent and the optimum moves with the design, so the sheet lays out a
series of reactions and leaves a column for what came out.

The anneal differs by dimensionality, which is the one substantive choice the
sheet makes for you: a 3D object needs the slow overnight ramp, a 2D one folds
on a ramp fast enough to run in an afternoon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dobladillo.constants import (
    ANNEAL_HOLD_C,
    ANNEAL_HOLD_MIN,
    ANNEAL_RAMP_2D_C_PER_MIN,
    ANNEAL_RAMP_3D_C_PER_H,
    ANNEAL_RAMP_FROM_C,
    ANNEAL_RAMP_TO_C,
    BUFFER_EDTA_MM,
    BUFFER_PH,
    BUFFER_TRIS_MM,
    MGCL2_SCREEN_MM,
    MGCL2_SCREEN_STEP_MM,
    SCAFFOLD_CONC_NM,
    STAPLE_EXCESS,
)


def magnesium_screen(
    *,
    low: float = MGCL2_SCREEN_MM[0],
    high: float = MGCL2_SCREEN_MM[1],
    step: float = MGCL2_SCREEN_STEP_MM,
) -> list[float]:
    """The Mg2+ series to fold in parallel, covering both ends of the range.

    The top of the range is included even when it does not land on a step: the
    documented screen is "5 to 20 mM in 2 mM steps", and stepping from 5 by 2
    stops at 19, quietly never testing the stated upper bound. A slightly
    uneven last interval is better than a range that does not cover what it
    claims to.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    if high < low:
        raise ValueError(f"high ({high}) is below low ({low})")
    points: list[float] = []
    value = low
    while value <= high + 1e-9:
        points.append(round(value, 3))
        value += step
    if points[-1] < high - 1e-9:
        points.append(round(high, 3))
    return points


@dataclass(frozen=True)
class Anneal:
    hold_c: float
    hold_min: float
    from_c: float
    to_c: float
    rate: float
    rate_unit: str

    @property
    def duration_h(self) -> float:
        span = self.from_c - self.to_c
        per_hour = self.rate if self.rate_unit == "C/h" else self.rate * 60.0
        return round(self.hold_min / 60.0 + span / per_hour, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "hold": {"temperature_c": self.hold_c, "minutes": self.hold_min},
            "ramp": {
                "from_c": self.from_c,
                "to_c": self.to_c,
                "rate": self.rate,
                "rate_unit": self.rate_unit,
            },
            "total_hours": self.duration_h,
        }


def anneal_for(dimensionality: str) -> Anneal:
    """The ramp to use. 3D is the slow one; 2D tolerates minutes per degree."""
    if dimensionality not in {"2D", "3D"}:
        raise ValueError(f"dimensionality must be '2D' or '3D', got {dimensionality!r}")
    if dimensionality == "3D":
        return Anneal(
            ANNEAL_HOLD_C,
            ANNEAL_HOLD_MIN,
            ANNEAL_RAMP_FROM_C,
            ANNEAL_RAMP_TO_C,
            ANNEAL_RAMP_3D_C_PER_H,
            "C/h",
        )
    return Anneal(
        ANNEAL_HOLD_C,
        ANNEAL_HOLD_MIN,
        ANNEAL_RAMP_FROM_C,
        ANNEAL_RAMP_TO_C,
        ANNEAL_RAMP_2D_C_PER_MIN,
        "C/min",
    )


def folding_protocol(
    *,
    part_name: str,
    dimensionality: str,
    scaffold_variant: str,
    scaffold_nm: float = SCAFFOLD_CONC_NM[0],
    staple_excess: float = STAPLE_EXCESS[0],
    reaction_volume_ul: float = 50.0,
) -> dict[str, Any]:
    """One protocol sheet: buffer, a Mg2+ series, an anneal, and what to record."""
    screen = magnesium_screen()
    anneal = anneal_for(dimensionality)
    return {
        "part": part_name,
        "buffer": {
            "tris_mm": BUFFER_TRIS_MM,
            "edta_mm": BUFFER_EDTA_MM,
            "ph": BUFFER_PH,
        },
        "magnesium_screen_mm": screen,
        "reactions": [
            {
                "id": f"{part_name}_mg{mg:g}",
                "mgcl2_mm": mg,
                "volume_ul": reaction_volume_ul,
                "scaffold": {"variant": scaffold_variant, "final_nm": scaffold_nm},
                "staples_final_nm_each": scaffold_nm * staple_excess,
            }
            for mg in screen
        ],
        "anneal": anneal.as_dict(),
        "purification": [
            "agarose gel extraction",
            "PEG precipitation",
            "100 kDa spin filters",
        ],
        "record_for_each_reaction": [
            "MgCl2 used",
            "gel: leading band position and smearing",
            "yield estimate",
            "which reaction went on to imaging",
        ],
        "note": (
            "these are starting points from the literature, not results. The Mg2+ "
            "optimum moves with the design, which is why this is a series and not "
            "a number. Record what was actually used with every downstream result: "
            "a prediction made at one salt is not comparable to a measurement at another."
        ),
    }

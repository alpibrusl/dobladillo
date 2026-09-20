"""A matched pair of rectangles that differ in exactly one thing.

One has the square lattice's over-winding cancelled by periodic deletions; the
other does not. Everything else -- scaffold, dimensions, staple layout, folding
protocol -- is identical, so the difference between them is attributable to the
correction and to nothing else.

Why a pair rather than one structure. A single measurement that agrees with a
prediction can agree by luck: the object is about the right size, the model
says about the right size, and neither is really being tested. A pair is a
controlled comparison, and the thing compared is the DIFFERENCE, which is much
harder to get right by accident.

Why a long, narrow rectangle. The lattice mismatch accumulates along the helix,
so twist is proportional to length, while cost is set by the total scaffold
routed. A 12 x 576 rectangle and a 22 x 320 one use the same scaffold and cost
the same in oligos, and the first twists nearly twice as far. Designing the
experiment for signal is free here; it is only a choice of two numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dobladilo.constants import HELICAL_REPEAT_BP, SQUARE_LATTICE_EFFECTIVE_REPEAT_BP
from dobladilo.parts.rectangle import Rectangle, rothemund_rectangle

#: The geometry this experiment uses. Long enough that the uncorrected variant
#: accumulates more than three quarters of a turn, wide enough to still read as
#: a rectangle in an image rather than as a floppy ribbon.
DEFAULT_HELICES = 12
DEFAULT_LENGTH = 576


def twist_per_bp_turns() -> float:
    """Turns of over-winding the square lattice adds per base pair.

    The lattice fixes crossovers so that 32 bp spans three turns, which is
    10.667 bp per turn; relaxed B-DNA wants 10.5. The difference is small and
    it accumulates.
    """
    return 1.0 / HELICAL_REPEAT_BP - 1.0 / SQUARE_LATTICE_EFFECTIVE_REPEAT_BP


def predicted_twist_degrees(length_bp: int) -> float:
    """End-to-end twist of an UNCORRECTED sheet of this length."""
    return length_bp * twist_per_bp_turns() * 360.0


@dataclass(frozen=True)
class TwistPair:
    corrected: Rectangle
    uncorrected: Rectangle
    predicted_twist_deg: float

    @property
    def shares_geometry(self) -> bool:
        """The pair is only controlled if the two differ in one thing."""
        return (
            self.corrected.helices == self.uncorrected.helices
            and self.corrected.length == self.uncorrected.length
            and self.corrected.scaffold.variant == self.uncorrected.scaffold.variant
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment": "twist_pair",
            "geometry": {
                "helices": self.corrected.helices,
                "length_bp": self.corrected.length,
                "approx_nm": self.corrected.as_dict()["approx_dimensions_nm"],
            },
            "differs_only_in": "periodic deletions that cancel the lattice over-winding",
            "predicted_twist_of_uncorrected_deg": round(self.predicted_twist_deg, 0),
            "arms": {
                "corrected": {
                    "deletions": self.corrected.scaffold.deletions,
                    "staples": self.corrected.staple_count,
                    "staple_nt": sorted(set(self.corrected.staple_lengths)),
                    "prediction": "lies flat on mica",
                },
                "uncorrected": {
                    "deletions": self.uncorrected.scaffold.deletions,
                    "staples": self.uncorrected.staple_count,
                    "staple_nt": sorted(set(self.uncorrected.staple_lengths)),
                    "prediction": (
                        "cannot lie flat: curls, rolls, or adsorbs as a distorted "
                        "parallelogram rather than a clean rectangle"
                    ),
                },
            },
            "readout": (
                "the FRACTION appearing as a clean rectangle, counted per arm. Mica "
                "adsorption flattens, so asking whether a single particle looks twisted "
                "is the wrong question; asking how many refuse to lie flat is not."
            ),
        }


def twist_pair(
    *,
    helices: int = DEFAULT_HELICES,
    length: int = DEFAULT_LENGTH,
    scaffold_variant: str = "p7249",
) -> TwistPair:
    """Both arms, built from the same call so they cannot drift apart."""
    # Written out rather than unpacked from a shared dict, so that the two
    # calls receiving identical arguments is visible on the page. This is the
    # one place where a difference between the arms would go unnoticed.
    pair = TwistPair(
        corrected=rothemund_rectangle(
            helices=helices,
            length=length,
            scaffold_variant=scaffold_variant,
            twist_corrected=True,
        ),
        uncorrected=rothemund_rectangle(
            helices=helices,
            length=length,
            scaffold_variant=scaffold_variant,
            twist_corrected=False,
        ),
        predicted_twist_deg=predicted_twist_degrees(length),
    )
    if not pair.shares_geometry:
        raise AssertionError("the arms differ in more than the correction")
    return pair

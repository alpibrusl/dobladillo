"""Comparing two arms of a matched pair, which is what the twist test measures.

E2 does not ask how big a particle is. It asks **what fraction lies flat as a
clean rectangle**, counted per arm, and whether the corrected arm does better
than the uncorrected one. That is a difference of two proportions, and it needs
an interval of its own -- quoting each arm's Wilson interval and eyeballing the
overlap is a known way to call a real difference insignificant.

The verdict has three outcomes and the third is not a failure. `docs/
TWIST_PAIR_EXPERIMENT.md` says it plainly: if both arms behave the same, the
correction is unnecessary and we stop building it into every design. So
"indistinguishable" is a result, and the code must be able to say it rather
than only being able to say "not significant".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from dobladillo.imaging.classify import Fraction, Population

#: Below this difference in flat fraction, the two arms are called the same
#: even when the interval excludes zero. A twist correction that buys two
#: percentage points is not worth deleting one base in every sixty-four from
#: every design that uses the lattice.
MATERIAL_DIFFERENCE = 0.10


@dataclass(frozen=True)
class ArmComparison:
    """Two arms of a matched pair, and whether they behave differently."""

    corrected: Fraction
    uncorrected: Fraction

    @property
    def difference(self) -> float:
        """Corrected minus uncorrected. Positive means the correction helped."""
        return self.corrected.value - self.uncorrected.value

    @property
    def ci95(self) -> tuple[float, float]:
        """Newcombe's score interval for the difference of two proportions.

        Built from the two Wilson intervals rather than from a normal
        approximation, for the same reason each of those is a Wilson interval:
        this measurement lives near 0 and 1, where the textbook interval runs
        off the end of the scale.
        """
        low_a, high_a = self.corrected.ci95
        low_b, high_b = self.uncorrected.ci95
        a, b = self.corrected.value, self.uncorrected.value
        lower = (a - b) - math.hypot(a - low_a, high_b - b)
        upper = (a - b) + math.hypot(high_a - a, b - low_b)
        return (max(-1.0, lower), min(1.0, upper))

    @property
    def distinguishable(self) -> bool:
        """Whether the interval excludes no difference at all."""
        low, high = self.ci95
        return low > 0 or high < 0

    @property
    def verdict(self) -> str:
        """One of three, and the third is a result rather than a shrug."""
        if not self.distinguishable:
            return "indistinguishable"
        if abs(self.difference) < MATERIAL_DIFFERENCE:
            return "distinguishable but immaterial"
        return "correction helps" if self.difference > 0 else "correction hurts"

    @property
    def correction_is_worth_it(self) -> bool:
        return self.verdict == "correction helps"

    def as_dict(self) -> dict[str, Any]:
        low, high = self.ci95
        return {
            "corrected": self.corrected.as_dict(),
            "uncorrected": self.uncorrected.as_dict(),
            "difference": round(self.difference, 4),
            "ci95": [round(low, 4), round(high, 4)],
            "distinguishable": self.distinguishable,
            "verdict": self.verdict,
            "material_threshold": MATERIAL_DIFFERENCE,
        }

    def summary(self) -> str:
        low, high = self.ci95
        return (
            f"flat fraction: corrected {self.corrected.value:.0%} "
            f"({self.corrected.count}/{self.corrected.total}), "
            f"uncorrected {self.uncorrected.value:.0%} "
            f"({self.uncorrected.count}/{self.uncorrected.total})\n"
            f"difference {self.difference:+.0%}, 95% [{low:+.0%}, {high:+.0%}] "
            f"-> {self.verdict}"
        )


def flat_fraction(population: Population) -> Fraction:
    """How many of the counted particles lay flat as a clean rectangle.

    `well_formed` alone, deliberately: `twisted` particles have the right
    footprint and did not lie flat, which is precisely what this experiment is
    counting, so folding them in would erase the measurement.
    """
    return Fraction(population.counts.get("well_formed", 0), population.total)


def compare_arms(corrected: Population, uncorrected: Population) -> ArmComparison:
    """The twist pair's readout."""
    return ArmComparison(corrected=flat_fraction(corrected), uncorrected=flat_fraction(uncorrected))

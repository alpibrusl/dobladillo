"""The twist pair's readout: a difference of two proportions, with a verdict."""

from __future__ import annotations

import pytest

from dobladillo.imaging.arms import (
    MATERIAL_DIFFERENCE,
    ArmComparison,
    compare_arms,
    flat_fraction,
)
from dobladillo.imaging.classify import Fraction, Population


def _pair(a: tuple[int, int], b: tuple[int, int]) -> ArmComparison:
    return ArmComparison(corrected=Fraction(*a), uncorrected=Fraction(*b))


def test_a_clear_difference_is_called() -> None:
    found = _pair((38, 40), (12, 40))
    assert found.difference == pytest.approx(0.65)
    assert found.distinguishable
    assert found.verdict == "correction helps"
    assert found.correction_is_worth_it


def test_no_difference_is_a_result_not_a_shrug() -> None:
    """The experiment document says so outright: if both arms behave the same,
    the correction is unnecessary and we stop building it into every design.
    Code that can only say 'not significant' cannot report that."""
    found = _pair((30, 40), (29, 40))
    assert found.verdict == "indistinguishable"
    assert not found.correction_is_worth_it


def test_a_real_but_tiny_difference_is_not_worth_the_deletions() -> None:
    """Large n makes a two-point difference statistically clear. Deleting one
    base in every sixty-four from every design on the lattice needs more than
    statistical clarity."""
    found = _pair((390, 400), (370, 400))
    assert found.distinguishable, "with n=400 this should clear zero"
    assert abs(found.difference) < MATERIAL_DIFFERENCE
    assert found.verdict == "distinguishable but immaterial"
    assert not found.correction_is_worth_it


def test_a_correction_that_hurts_is_named() -> None:
    found = _pair((10, 40), (35, 40))
    assert found.verdict == "correction hurts"


def test_the_interval_is_on_the_difference_not_on_each_arm() -> None:
    """Quoting each arm's interval and eyeballing the overlap is a known way
    to call a real difference insignificant. Two arms whose Wilson intervals
    overlap can still have a difference interval that excludes zero."""
    found = _pair((32, 40), (22, 40))
    low_a, high_a = found.corrected.ci95
    low_b, high_b = found.uncorrected.ci95
    assert low_a < high_b, "the per-arm intervals overlap"
    assert found.distinguishable, "yet the difference clears zero"


def test_the_interval_widens_as_counts_shrink() -> None:
    wide = _pair((8, 10), (3, 10))
    narrow = _pair((800, 1000), (300, 1000))
    assert wide.difference == pytest.approx(narrow.difference, abs=0.01)
    w = wide.ci95[1] - wide.ci95[0]
    n = narrow.ci95[1] - narrow.ci95[0]
    assert w > 4 * n


def test_twisted_particles_are_not_counted_as_flat() -> None:
    """The measurement itself. A twisted particle has the right footprint and
    did not lie flat, which is exactly what is being counted -- folding it in
    with `well_formed` would erase the experiment."""
    population = Population(
        counts={"well_formed": 20, "twisted": 15, "malformed": 4, "aggregate": 1},
        total=40,
        well_formed=Fraction(20, 40),
        excluded_at_edge=0,
    )
    assert flat_fraction(population) == Fraction(20, 40)


def test_compare_arms_reads_the_populations() -> None:
    def pop(flat: int, twisted: int) -> Population:
        total = flat + twisted
        return Population(
            counts={"well_formed": flat, "twisted": twisted, "malformed": 0, "aggregate": 0},
            total=total,
            well_formed=Fraction(flat, total),
            excluded_at_edge=0,
        )

    found = compare_arms(pop(36, 4), pop(11, 29))
    assert found.verdict == "correction helps"
    assert "flat fraction" in found.summary()

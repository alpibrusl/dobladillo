"""The pair is only evidence if the two arms differ in exactly one thing.

Everything here guards that. A pair whose arms drift apart in scaffold, size or
staple layout measures the drift as well as the correction, and there is no way
to tell afterwards which produced the difference.
"""

from __future__ import annotations

import pytest

from dobladilo.lab.plates import name_and_assign_wells
from dobladilo.parts.twist_pair import (
    predicted_twist_degrees,
    twist_pair,
    twist_per_bp_turns,
)
from dobladilo.routing.rules import lint


@pytest.fixture(scope="module")
def pair():
    return twist_pair()


def test_the_arms_differ_only_in_the_correction(pair) -> None:
    assert pair.shares_geometry
    assert pair.corrected.helices == pair.uncorrected.helices
    assert pair.corrected.length == pair.uncorrected.length
    assert pair.corrected.staple_count == pair.uncorrected.staple_count
    assert pair.corrected.scaffold.deletions > 0
    assert pair.uncorrected.scaffold.deletions == 0


def test_both_arms_pass_the_design_rules(pair) -> None:
    """An uncorrected arm that broke a hard rule would confound the experiment:
    a failure to fold could then be blamed on either cause."""
    for arm in (pair.corrected, pair.uncorrected):
        report = lint(arm.design)
        assert report.ok, [v.as_dict() for v in report.hard]


def test_the_correction_is_what_shortens_staples(pair) -> None:
    """A deletion removes a base from whichever staple spans it, so the
    corrected arm carries staples below the preferred band and the uncorrected
    one does not. Worth pinning: it is the correction's cost, not a defect."""
    assert set(pair.uncorrected.staple_lengths) == {32}
    assert 30 in set(pair.corrected.staple_lengths)


def test_twist_accumulates_with_length_not_width() -> None:
    """Which is the whole reason the experiment uses a long, narrow rectangle."""
    assert predicted_twist_degrees(576) == pytest.approx(2 * predicted_twist_degrees(288))
    short = twist_pair(helices=22, length=320)
    long_ = twist_pair(helices=12, length=576)
    assert long_.predicted_twist_deg > 1.7 * short.predicted_twist_deg


def test_the_two_geometries_cost_about_the_same() -> None:
    """Signal is nearly free here: same scaffold, same money, more twist."""
    short = twist_pair(helices=22, length=320)
    long_ = twist_pair(helices=12, length=576)
    cost = lambda arm: name_and_assign_wells(arm.design).cost.total  # noqa: E731
    assert abs(cost(short.corrected) - cost(long_.corrected)) < 60


def test_the_lattice_really_does_overwind() -> None:
    """A negative or zero mismatch would mean there is nothing to correct and
    the whole experiment is pointless."""
    assert twist_per_bp_turns() > 0


def test_the_uncorrected_arm_twists_past_a_half_turn(pair) -> None:
    """Below roughly half a turn the two arms would be hard to tell apart on a
    surface that flattens what it adsorbs."""
    assert pair.predicted_twist_deg > 180

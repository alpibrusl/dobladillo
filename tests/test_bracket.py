"""The measurement window, and the ladder that guarantees landing inside it."""

from __future__ import annotations

import math

import pytest

from dobladillo.hamiltonian.bracket import (
    DESIGN_MAGNESIUM_M,
    DESIGN_TEMPERATURE_K,
    MAX_HOMOPOLYMER_RUN,
    candidate_latches,
    informative_half_width_kt,
    informative_window_kt,
    is_informative,
    ladder,
    latch_sequence,
    probability,
)
from dobladillo.sequence.thermo import duplex, gc_fraction, is_self_complementary, latch_field_kt


def test_the_window_is_about_three_kt() -> None:
    assert informative_half_width_kt() == pytest.approx(0.5 * math.log(19.0))
    assert informative_window_kt() == pytest.approx(2.944, abs=0.001)


def test_probability_and_field_are_inverse() -> None:
    for h in (-3.0, -0.5, 0.0, 0.5, 3.0):
        p = probability(h)
        assert 0.5 * math.log(p / (1 - p)) == pytest.approx(h)


def test_the_window_edges_are_the_stated_probabilities() -> None:
    assert is_informative(informative_half_width_kt() - 1e-9)
    assert not is_informative(informative_half_width_kt() + 1e-3)
    assert probability(informative_half_width_kt()) == pytest.approx(0.95)


@pytest.mark.parametrize("length", range(4, 13))
def test_latch_sequences_have_the_composition_they_claim(length: int) -> None:
    for gc in range(length + 1):
        s = latch_sequence(length=length, gc=gc)
        assert len(s) == length
        assert gc_fraction(s) == pytest.approx(gc / length)


def test_candidates_are_all_usable_as_latches() -> None:
    for s in candidate_latches():
        assert not is_self_complementary(s)
        runs = [len(list(g)) for g in __import__("itertools").groupby(s)]
        assert max(runs) <= MAX_HOMOPOLYMER_RUN


def test_the_ladder_leaves_no_gap() -> None:
    """The guarantee. A gap wider than the window is an offset for which every
    rung reads p = 0 or p = 1, which is the failure the ladder exists to stop."""
    rungs = ladder()
    assert rungs.covers_its_range
    assert rungs.largest_gap_kt <= rungs.window_kt


def test_every_offset_in_range_has_an_informative_rung() -> None:
    rungs = ladder()
    low, high = rungs.offset_range_kt
    # The open interval: the endpoints are where p is exactly 0.95, and whether
    # floating point lands a hair inside or outside is not a property of the
    # design. An offset that close to the edge is not measurable anyway.
    for i in range(1, 100):
        offset = low + (high - low) * i / 100.0
        assert rungs.rung_for(offset) is not None, f"no rung for an offset of {offset:.2f} kT"


def test_an_offset_outside_the_range_is_reported_rather_than_approximated() -> None:
    rungs = ladder()
    low, high = rungs.offset_range_kt
    assert rungs.rung_for(low - 5.0) is None
    assert rungs.rung_for(high + 5.0) is None


def test_the_ladder_is_not_wastefully_long() -> None:
    """Each rung is an oligo set. The covering greedy should need roughly the
    span divided by the window, not many more."""
    rungs = ladder()
    low, high = rungs.span_kt
    assert len(rungs.rungs) <= math.ceil((high - low) / rungs.window_kt) + 1


def test_stage0s_own_latch_sweep_would_not_have_covered_anything() -> None:
    """The finding. Stage 0 sweeps 5 to 10 bp at balanced GC, which spans about
    six kT of field -- but the conformational offset slides the whole sweep by
    an unknown amount first, and six kT of sweep can sit entirely outside a
    three kT window. Checked here as the concrete statement that for some
    plausible offsets NO construct in that sweep reads informatively."""
    fields = [
        latch_field_kt(
            duplex(latch_sequence(length=n, gc=n // 2), magnesium_m=DESIGN_MAGNESIUM_M),
            temperature_k=DESIGN_TEMPERATURE_K,
        )
        for n in (5, 6, 7, 8, 9, 10)
    ]
    blind = [
        offset
        for offset in range(0, 45)
        if not any(is_informative(h - offset / 2.0) for h in fields)
    ]
    assert blind, "if this ever passes trivially the sweep is fine and the ladder is redundant"
    assert len(blind) > 10, f"only {len(blind)} blind offsets, expected many"

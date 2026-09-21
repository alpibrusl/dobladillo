"""The constants are load-bearing, so the relationships between them are pinned.

These are not tests of arithmetic. Each one encodes a fact about the domain
that would otherwise only exist in a comment, and would therefore survive a
careless edit.
"""

from __future__ import annotations

import pytest

from dobladillo import units
from dobladillo.constants import (
    HELICAL_REPEAT_BP,
    SQUARE_LATTICE_EFFECTIVE_REPEAT_BP,
    STAPLE_LENGTH_NT,
    STAPLE_LENGTH_TARGET_NT,
    STAPLE_MIN_DOMAIN_NT,
    STAPLE_SEED_DOMAIN_NT,
    Lattice,
)


def test_honeycomb_period_is_twist_neutral() -> None:
    """21 bp is exactly two turns at the relaxed repeat: no built-in twist."""
    assert pytest.approx(HELICAL_REPEAT_BP) == Lattice.HONEYCOMB_PERIOD_BP / 2.0


def test_square_lattice_overwinds() -> None:
    """32 bp over 3 turns is 10.67 bp/turn, above the relaxed 10.5.

    That difference is the whole reason square-lattice objects come out with a
    right-handed global twist unless corrected by periodic deletions.
    """
    assert pytest.approx(10.667, abs=1e-3) == SQUARE_LATTICE_EFFECTIVE_REPEAT_BP
    assert SQUARE_LATTICE_EFFECTIVE_REPEAT_BP > HELICAL_REPEAT_BP


def test_staple_target_sits_inside_the_allowed_range() -> None:
    assert STAPLE_LENGTH_NT[0] <= STAPLE_LENGTH_TARGET_NT[0]
    assert STAPLE_LENGTH_TARGET_NT[1] <= STAPLE_LENGTH_NT[1]


def test_a_seed_domain_is_longer_than_the_minimum_domain() -> None:
    """A seed that did not exceed the floor would make the seed rule vacuous."""
    assert STAPLE_SEED_DOMAIN_NT > STAPLE_MIN_DOMAIN_NT


def test_a_staple_can_hold_at_least_two_seed_domains() -> None:
    """Otherwise no staple could ever bridge two helices with a firm grip."""
    assert STAPLE_LENGTH_NT[1] >= 2 * STAPLE_SEED_DOMAIN_NT


@pytest.mark.parametrize("nm", [0.0, 0.8518, 3.4, 100.0])
def test_oxdna_conversion_round_trips(nm: float) -> None:
    assert units.oxdna_to_nm(units.nm_to_oxdna(nm)) == pytest.approx(nm)


def test_one_oxdna_unit_is_the_documented_length() -> None:
    assert units.oxdna_to_nm(1.0) == pytest.approx(0.8518)

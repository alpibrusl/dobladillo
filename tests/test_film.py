"""A coupled film, and the result that matters commercially: it is robust."""

from __future__ import annotations

import pytest

from dobladillo.hamiltonian.film import (
    hill_coefficient,
    occupancy,
    square_lattice,
    switch_width_kt,
)

#: Latch bias shifts by this much per kelvin, from `sequence.thermo` on a
#: balanced 8 bp latch at 12 mM Mg. Used only to state widths in degrees.
KT_PER_KELVIN = 0.162


def _film(rows, cols, **kw):
    return square_lattice(rows, cols, coupling_kt=1.0, **kw)


def test_an_isolated_switch_is_a_poor_threshold() -> None:
    """The baseline the whole idea has to beat: about 14 C."""
    lone = square_lattice(1, 1, coupling_kt=0.0)
    assert switch_width_kt(lone) == pytest.approx(2.2, abs=0.1)
    assert switch_width_kt(lone) / KT_PER_KELVIN > 12


def test_geometry_buys_more_than_coupling_strength() -> None:
    """A pair with strong coupling stays gradual; a lattice with the same
    coupling does not. Neighbour count, not bond strength, is the lever."""
    strong_pair = square_lattice(1, 2, coupling_kt=2.0)
    weak_film = square_lattice(3, 4, coupling_kt=1.0)
    assert switch_width_kt(weak_film) < switch_width_kt(strong_pair)


def test_a_scaffold_sized_film_switches_inside_two_degrees() -> None:
    """3x4 is what fits on one M13 scaffold as 4-helix hinges."""
    film = _film(3, 4)
    assert switch_width_kt(film) / KT_PER_KELVIN < 2.0
    assert hill_coefficient(film) > 20


def test_the_transition_survives_the_scatter_stage_zero_gates_on() -> None:
    """The commercially decisive result, and it inverts the programme's own
    worry. Stage 0 gates at 0.3 kT because resolving ONE coupling needs that.
    A film averages over its couplings instead, so the same disorder barely
    moves it."""
    clean = switch_width_kt(_film(3, 4))
    dirty = [switch_width_kt(_film(3, 4, coupling_scatter_kt=0.3, seed=s)) for s in range(5)]
    assert max(dirty) < 1.5 * clean


def test_it_does_finally_degrade() -> None:
    """The claim is robustness, not immunity. If this ever passes trivially the
    disorder is not being applied."""
    clean = switch_width_kt(_film(3, 4))
    wrecked = [switch_width_kt(_film(3, 4, coupling_scatter_kt=1.5, seed=s)) for s in range(5)]
    assert sum(wrecked) / len(wrecked) > 2 * clean


def test_disorder_belongs_to_the_object_not_to_the_sweep() -> None:
    """A film is one physical thing: its defects do not resample as it warms.
    Re-drawing per point would average the disorder away and report a
    sharpness no real film has."""
    a = _film(3, 4, coupling_scatter_kt=0.5, seed=1)
    b = _film(3, 4, coupling_scatter_kt=0.5, seed=1)
    assert (a.J == b.J).all()
    c = _film(3, 4, coupling_scatter_kt=0.5, seed=2)
    assert not (a.J == c.J).all()


def test_occupancy_is_monotonic_in_the_field() -> None:
    film = _film(3, 4)
    values = [occupancy(film, f) for f in (-3.0, -1.0, 0.0, 1.0, 3.0)]
    assert values == sorted(values)
    assert occupancy(film, 0.0) == pytest.approx(0.5, abs=0.02)

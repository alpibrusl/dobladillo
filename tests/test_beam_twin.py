"""The fast predictor's synthetic twin: designs whose shape a textbook knows.

Graded here as an agent would grade a change to `mechanics.beam`, and shown
able to fail: a predictor with the wrong stiffness, a flipped sign, or one
that answers "straight" to everything must each be caught.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pytest

from dobladillo.mechanics import beam
from dobladillo.mechanics.twin import (
    TWIN_PARAMETERS,
    composite_beam,
    grade,
    shortened_bundle,
    standard_twins,
)


@pytest.fixture(scope="module")
def twins() -> tuple[Any, ...]:
    return standard_twins()


def test_the_predictor_reproduces_every_twin(twins: tuple[Any, ...]) -> None:
    graded = grade(twins)
    assert all(g.ok for g in graded), [g.as_dict() for g in graded if not g.ok]


def test_the_answers_are_the_textbook_ones(twins: tuple[Any, ...]) -> None:
    """Pinned against the closed form for a hexagon, written out separately:
    R = (3 S D^2 + 6 EI) / (S eps D)."""
    p = TWIN_PARAMETERS
    S, EI, D = p.stretch_pn, p.bend_pn_nm2, p.interhelix_nm
    closed = (3 * S * D**2 + 6 * EI) / (S * D / 21)
    by_name = {t.name: t for t in twins}
    assert by_name["6hb shortened: helix 0 1/21"].radius_nm == pytest.approx(closed, rel=1e-9)
    assert by_name["6hb shortened: helix 0 1/42"].radius_nm == pytest.approx(2 * closed, rel=1e-9)
    assert closed == pytest.approx(168.0, abs=0.05)
    # opposite helices bend opposite ways
    a = by_name["6hb shortened: helix 0 1/21"].direction_deg
    b = by_name["6hb shortened: helix 3 1/21"].direction_deg
    assert abs((a - b) % 360.0 - 180.0) < 1e-6
    assert by_name["6hb shortened: helices 0 and 3, opposite"].straight
    assert by_name["6hb unmodified"].straight


def _predictor(tamper: Any) -> Any:
    def run(design: Any, parameters: Any) -> Any:
        return tamper(beam.predict(design, parameters), design, parameters)

    return run


def test_a_predictor_with_the_wrong_stiffness_fails(twins: tuple[Any, ...]) -> None:
    def stiffer(_: Any, design: Any, p: Any) -> Any:
        return beam.predict(design, dataclasses.replace(p, bend_pn_nm2=2 * p.bend_pn_nm2))

    graded = grade(twins, predictor=_predictor(stiffer))
    assert [g.ok for g in graded] == [False, False, False, True, True]


def test_a_predictor_bending_the_wrong_way_fails(twins: tuple[Any, ...]) -> None:
    def flipped(shape: Any, *_: Any) -> Any:
        return dataclasses.replace(
            shape, bend_direction_deg=(shape.bend_direction_deg + 180.0) % 360.0
        )

    graded = grade(twins, predictor=_predictor(flipped))
    assert [g.ok for g in graded] == [False, False, False, True, True]


def test_a_predictor_that_always_says_straight_fails(twins: tuple[Any, ...]) -> None:
    def lazy(shape: Any, *_: Any) -> Any:
        return dataclasses.replace(shape, curvature_per_nm=0.0, radius_nm=math.inf)

    graded = grade(twins, predictor=_predictor(lazy))
    assert [g.ok for g in graded] == [False, False, False, True, True]


def test_a_symmetric_twin_bent_one_sided_fails() -> None:
    """The straight twins are not graded by a threshold loose enough to pass
    a real bend: a symmetric twin predicted as bent as one helix is fails."""
    (symmetric,) = [t for t in standard_twins() if "opposite" in t.name]
    one_sided = shortened_bundle({0: 21})

    def swap(_: Any, design: Any, p: Any) -> Any:
        return beam.predict(one_sided.design, p)

    assert not grade([symmetric], predictor=_predictor(swap))[0].ok


def test_deletions_on_a_crossover_are_refused() -> None:
    with pytest.raises(ValueError, match="would land on crossovers"):
        shortened_bundle({0: 1})


def test_the_formula_refuses_a_section_that_is_not_isotropic() -> None:
    line = {0: np.array([-2.5, 0.0]), 1: np.array([0.0, 0.0]), 2: np.array([2.5, 0.0])}
    with pytest.raises(ValueError, match="not isotropic"):
        composite_beam(line, {0: 1 / 21}, TWIN_PARAMETERS)

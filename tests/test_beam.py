"""The beam model, checked against things it did not produce.

A reimplementation without an independent reference is how this project's
worst silent bugs got in (VISION.md section 0). So: the matrix is checked for
the properties any correct stiffness matrix has, the solve against a textbook
formula, and its reach -- what it cannot see -- is pinned rather than hoped
away.
"""

from __future__ import annotations

import numpy as np
import pytest
import scadnano as sc

from dobladillo.mechanics.beam import BeamParameters, assemble, predict
from dobladillo.parts.bundle import END_NT, six_helix_bundle
from dobladillo.parts.twist_pair import twist_pair


def _one_helix_shortened() -> sc.Design:
    """The 6HB with a deletion every 21 bp on helix 0 only, mid-domain."""
    design = six_helix_bundle().design
    for offset in range(END_NT + 3, END_NT + 1176, 21):
        design.add_deletion(0, offset)
    return design


@pytest.fixture(scope="module")
def bundle_system():
    return assemble(six_helix_bundle().design, BeamParameters())


def test_the_stiffness_matrix_is_symmetric(bundle_system) -> None:
    K = bundle_system.K
    assert abs(K - K.T).max() < 1e-6


@pytest.mark.parametrize("mode", ["translate", "rotate"])
def test_rigid_motion_costs_nothing(bundle_system, mode: str) -> None:
    """A stiffness matrix that resists rigid motion has a sign or a lever arm
    wrong somewhere. Only the pinned node may push back."""
    X = bundle_system.X
    u = np.zeros((len(X), 6))
    if mode == "translate":
        u[:, :3] = [0.3, -0.2, 0.1]
    else:
        omega = np.array([1e-3, -2e-3, 3e-3])
        u[:, :3] = np.cross(omega, X)
        u[:, 3:] = omega
    force = (bundle_system.K @ u.ravel()).reshape(-1, 6)
    force[0] = 0.0  # the pinned node
    assert np.abs(force).max() < 1e-6 * np.abs(bundle_system.K).max()


def test_a_shortened_helix_bends_the_bundle_as_composite_beam_theory_says() -> None:
    """The textbook answer: helix 0 wants to be 1/21 shorter, the section is
    six helices on a hexagon of circumradius D, so

        kappa = S * eps * D / (S * 6 D^2 / 2 + 6 EI),   R = 168.0 nm here.

    Twist-stretch coupling is switched off, because the formula has none.
    """
    p = BeamParameters(twist_stretch_pn_nm=0.0)
    S, EI, D = p.stretch_pn, p.bend_pn_nm2, p.interhelix_nm
    expected = (S * 6 * D**2 / 2 + 6 * EI) / (S * (1 / 21) * D)
    result = predict(_one_helix_shortened(), p)
    assert result.radius_nm == pytest.approx(expected, rel=0.01)
    # ... toward the short helix, which sits at 270 deg from the centroid
    assert result.bend_direction_deg == pytest.approx(270.0, abs=1.0)


def test_rigid_crossovers_really_are_rigid() -> None:
    """CanDo treats crossovers as rigid. Ours are springs, so check that a
    hundredfold change in their stiffness does not move the answer."""
    soft = predict(_one_helix_shortened(), BeamParameters(1100, 230, 460, -90, 1e3, 1e3))
    hard = predict(_one_helix_shortened(), BeamParameters(1100, 230, 460, -90, 1e5, 1e5))
    assert soft.radius_nm == pytest.approx(hard.radius_nm, rel=0.01)


def test_a_correctly_phased_bundle_is_straight_and_untwisted() -> None:
    result = predict(six_helix_bundle().design)
    assert result.radius_nm > 1e5
    assert abs(result.twist_deg) < 1.0


def test_the_square_lattice_twists_unless_corrected() -> None:
    """E2's premise, from mechanics instead of arithmetic. The uncorrected arm
    twists right-handed (positive), by less than the 309 deg the lattice
    arithmetic gives, because the sheet's own stiffness resists part of it;
    the corrected arm barely twists."""
    pair = twist_pair()
    uncorrected = predict(pair.uncorrected.design)
    corrected = predict(pair.corrected.design)
    assert 180 < uncorrected.twist_deg < pair.predicted_twist_deg
    assert abs(corrected.twist_deg) < 0.15 * uncorrected.twist_deg


def test_misphased_crossovers_are_invisible_to_this_model() -> None:
    """Its known blind spot, pinned. This bundle bends to a 269 nm radius in
    oxDNA because two of its three crossover pairs are off-phase. A model
    that places every crossover on its lattice position cannot see that; the
    `crossover_azimuth` rule does. If this test starts failing, the model has
    changed class and its docstring must change with it."""
    design = sc.Design.from_scadnano_file("tests/data/our_designs/bundle_21_21.sc")
    assert predict(design).radius_nm > 1e5

    from dobladillo.routing.azimuth import measure

    assert not measure(design).acceptable


def test_it_answers_in_seconds() -> None:
    assert predict(six_helix_bundle().design).seconds < 5.0

"""The gap between the designed Hamiltonian and the one that exists.

Two results here are findings about the plan rather than tests of the code, and
both are pinned so that a later change cannot quietly undo them.
"""

from __future__ import annotations

import numpy as np
import pytest

from dobladilo.hamiltonian.discrepancy import (
    Noise,
    noise_floor,
    observe,
    realise,
    recover_two_spin,
)
from dobladilo.hamiltonian.model import Ising


def _pair(coupling: float) -> Ising:
    return Ising(h=np.zeros(2), J=np.array([[0.0, coupling], [coupling, 0.0]]))


# ------------------------------------------------------------- realisation


def test_a_perfect_process_returns_the_design_unchanged() -> None:
    rng = np.random.default_rng(0)
    designed = _pair(1.4)
    built = realise(designed, Noise(synthesis_kt=0.0), rng=rng)
    assert built.couplings == pytest.approx(designed.couplings)
    assert built.h == pytest.approx(designed.h)


def test_context_terms_act_on_couplings_and_fields_together() -> None:
    """Both are set by the same latch chemistry: if origami context shifts a
    latch's free energy it shifts the bias it sets and the coupling it mediates
    at once. Treating them independently would model two errors where there is
    one."""
    rng = np.random.default_rng(1)
    designed = Ising(h=np.array([1.0, 1.0]), J=np.array([[0.0, 2.0], [2.0, 0.0]]))
    built = realise(designed, Noise(synthesis_kt=0.0, context_slope=0.5), rng=rng)
    assert built.couplings[0] == pytest.approx(1.0)
    assert built.h == pytest.approx([0.5, 0.5])


def test_synthesis_scatter_is_zero_mean() -> None:
    rng = np.random.default_rng(2)
    designed = _pair(1.0)
    drawn = [realise(designed, Noise(synthesis_kt=0.4), rng=rng).couplings[0] for _ in range(400)]
    assert np.mean(drawn) == pytest.approx(1.0, abs=0.05)


# -------------------------------------------------------------- noise floor


def test_a_one_kt_coupling_survives_modest_scatter_and_not_more() -> None:
    """HAMILTONIAN.md section 7's third question, answered with a number."""
    floor = {r["synthesis_kt"]: r for r in noise_floor(1.0, levels=(0.1, 0.3, 0.8))}
    assert floor[0.1]["within_tolerance"]
    assert floor[0.3]["within_tolerance"]
    assert not floor[0.8]["within_tolerance"]


def test_the_documents_stage_zero_threshold_is_too_loose() -> None:
    """A finding about the plan, not about the code.

    Stage 0's go/no-go asks that construct-to-construct spread be below about
    1 kT. At 1 kT of spread, a designed 1 kT coupling comes back with a median
    error near 0.85 kT, which fails Stage 1's own requirement that J be
    constant to 0.3 kT. The gate should be roughly 0.3 kT, not 1.
    """
    at_one = noise_floor(1.0, levels=(1.0,), repeats=30)[0]
    assert at_one["median_error_kt"] > 0.6
    assert not at_one["within_tolerance"]


def test_an_unmeasurable_construct_is_counted_not_averaged_away() -> None:
    """A construct so extreme that a state never appears is an absent
    measurement, not a large error. Averaging over only the survivors at high
    scatter would look reassuring."""
    extreme = noise_floor(1.0, levels=(3.0,), repeats=30, depth=200_000)[0]
    assert extreme["unmeasurable"] > 0
    assert not extreme["within_tolerance"]


# ---------------------------------------------------------- ligation bias


@pytest.mark.parametrize("bias", [(0.6, 0.6), (0.0, 0.6), (0.4, -0.4)])
def test_a_per_spin_ligation_bias_cannot_corrupt_the_coupling(
    bias: tuple[float, float],
) -> None:
    """Sharper than section 6.4's warning, and derivable rather than lucky.

    A bias depending on each spin separately multiplies p(s) by
    exp(sum_i b_i [s_i = +1]), which is algebraically a shift in the fields.
    Fields do not enter J in a pairwise model, so J is untouched -- whether the
    bias is the same at both sites or different.
    """
    result = recover_two_spin(1.0, Noise(synthesis_kt=0.0, ligation_bias=bias), depth=4_000_000)
    assert result.coupling_error < 0.01


def test_a_per_spin_bias_does_land_in_the_fields() -> None:
    """Which is where it must be corrected, and where it is visible."""
    clean = recover_two_spin(1.0, Noise(synthesis_kt=0.0), depth=4_000_000)
    biased = recover_two_spin(
        1.0, Noise(synthesis_kt=0.0, ligation_bias=(0.6, 0.6)), depth=4_000_000
    )
    assert abs(clean.recovered_field_bias) < 0.02
    assert biased.recovered_field_bias > 0.3


@pytest.mark.parametrize("pair_bias", [0.2, 0.5, 1.0])
def test_a_joint_state_bias_corrupts_the_coupling_by_half_its_size(
    pair_bias: float,
) -> None:
    """The one form of readout bias that can reach J, and by an exact amount.

    An efficiency that differs when the two neighbours agree cannot be absorbed
    into fields, and it adds exactly half itself to the apparent coupling. That
    is what Stage 1's calibration has to rule out: not per-site efficiency, but
    dependence on the neighbour's state.
    """
    result = recover_two_spin(
        1.0, Noise(synthesis_kt=0.0, ligation_pair_bias=pair_bias), depth=4_000_000
    )
    assert result.recovered_coupling == pytest.approx(1.0 + pair_bias / 2, abs=0.01)


# ------------------------------------------------------------------ counts


def test_observation_returns_the_requested_depth() -> None:
    rng = np.random.default_rng(3)
    counts = observe(_pair(1.0), Noise(), 50_000, rng=rng)
    assert counts.sum() == 50_000
    assert len(counts) == 4

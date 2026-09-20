"""The inverse problem, checked against answers known before the code ran.

This is the gate HAMILTONIAN.md section 7 asks for, in test form: if the
pipeline cannot recover a Hamiltonian it was handed, it will not recover one it
was not. Every test here starts from parameters chosen, not fitted.
"""

from __future__ import annotations

import numpy as np
import pytest

from dobladilo.hamiltonian.inverse import (
    REALISABLE_COUPLINGS_KT,
    design,
    kl_divergence,
    quantise,
    solve,
)
from dobladilo.hamiltonian.model import (
    MAX_EXACT_SPINS,
    Ising,
    all_states,
    distribution,
    moments,
    two_spin_coupling,
)


def _random_model(n: int, seed: int, scale: float = 0.7) -> Ising:
    rng = np.random.default_rng(seed)
    coupling = np.triu(rng.normal(0, scale, (n, n)), k=1)
    return Ising(h=rng.normal(0, scale, n), J=coupling + coupling.T)


def _chain(n: int) -> np.ndarray:
    mask = np.zeros((n, n), dtype=bool)
    for i in range(n - 1):
        mask[i, i + 1] = mask[i + 1, i] = True
    return mask


# ------------------------------------------------------------------- model


def test_the_model_rejects_a_coupling_matrix_that_is_not_one() -> None:
    with pytest.raises(ValueError, match="symmetric"):
        Ising(h=np.zeros(2), J=np.array([[0.0, 1.0], [2.0, 0.0]]))
    with pytest.raises(ValueError, match="zero diagonal"):
        Ising(h=np.zeros(2), J=np.array([[1.0, 0.0], [0.0, 1.0]]))


@pytest.mark.parametrize(
    ("coupling", "h1", "h2"), [(0.8, 0.3, -0.5), (-1.2, 0.0, 0.0), (2.0, 1.5, 1.5)]
)
def test_the_forward_model_reproduces_the_documents_exact_formula(
    coupling: float, h1: float, h2: float
) -> None:
    """HAMILTONIAN.md section 4 gives J = ln[p(++)p(--)/p(+-)p(-+)]/4, exactly,
    and independently of the fields. It holds under exactly one sign
    convention, so this is the check that ours is that one -- and a sign error
    here would produce numbers that look entirely reasonable."""
    model = Ising(h=np.array([h1, h2]), J=np.array([[0.0, coupling], [coupling, 0.0]]))
    states, probabilities = distribution(model)
    table = {(int(s[0]), int(s[1])): float(p) for s, p in zip(states, probabilities, strict=True)}
    assert two_spin_coupling(table) == pytest.approx(coupling, abs=1e-9)


def test_a_positive_coupling_favours_agreement() -> None:
    """The other half of the convention, stated as behaviour rather than sign."""
    states, probabilities = distribution(Ising(h=np.zeros(2), J=np.array([[0.0, 1.0], [1.0, 0.0]])))
    agree = probabilities[(states[:, 0] == states[:, 1])].sum()
    assert agree > 0.8


def test_probabilities_sum_to_one_and_moments_are_bounded() -> None:
    model = _random_model(6, seed=1)
    _, probabilities = distribution(model)
    assert probabilities.sum() == pytest.approx(1.0)
    magnetisation, correlation = moments(model)
    assert np.all(np.abs(magnetisation) <= 1.0)
    assert np.all(np.abs(correlation) <= 1.0 + 1e-12)
    assert np.allclose(np.diag(correlation), 1.0)


def test_enumeration_refuses_rather_than_grinding() -> None:
    """Exact is exponential. Past the cap the honest answer is to say so, not
    to return something approximate that looks exact."""
    with pytest.raises(ValueError, match="exponential"):
        all_states(MAX_EXACT_SPINS + 1)


# ----------------------------------------------------------------- recovery


@pytest.mark.parametrize("n", [3, 5, 8])
def test_a_known_hamiltonian_is_recovered(n: int) -> None:
    """The gate. Anything that fails here fails on real data too."""
    truth = _random_model(n, seed=n)
    _, target = distribution(truth)
    fit = solve(target, n=n)

    assert fit.converged, fit.as_dict()
    assert np.abs(fit.model.h - truth.h).max() < 1e-4
    assert np.abs(fit.model.couplings - truth.couplings).max() < 1e-4


def test_recovery_survives_a_quasi_newton_step_count_plain_ascent_could_not() -> None:
    """Measured, not assumed: plain gradient ascent with a fixed step converged
    in 64 iterations at 3 spins, took 2306 at 5, and failed outright at 8,
    still 0.35 kT out after twenty thousand. The programme wants 25 to 100."""
    truth = _random_model(8, seed=8)
    _, target = distribution(truth)
    fit = solve(target, n=8)
    assert fit.converged
    assert fit.iterations < 1000


def test_couplings_outside_the_mask_stay_exactly_zero() -> None:
    """Not fitted and then deleted: a coupling that is fitted and then removed
    takes its explanatory work with it, and nothing compensates."""
    n = 6
    _, target = distribution(_random_model(n, seed=2))
    fit = solve(target, n=n, allowed=_chain(n))
    forbidden = ~_chain(n)
    np.fill_diagonal(forbidden, False)
    assert np.all(fit.model.J[forbidden] == 0.0)


# ------------------------------------------------------------- manufacturing


def test_quantising_lands_on_what_can_be_built() -> None:
    model = _random_model(5, seed=4, scale=2.0)
    built = quantise(model)
    assert set(np.round(built.couplings, 6)) <= set(REALISABLE_COUPLINGS_KT)
    ladder = np.arange(-10.0, 10.5, 0.5)
    assert all(np.isclose(value, ladder).any() for value in built.h)


def test_the_field_ladder_is_clipped_not_wrapped() -> None:
    """A bias the ladder cannot reach must saturate, never fold around."""
    model = Ising(h=np.array([50.0, -50.0]), J=np.zeros((2, 2)))
    built = quantise(model)
    assert built.h[0] == pytest.approx(10.0)
    assert built.h[1] == pytest.approx(-10.0)


def test_the_decomposition_separates_the_two_costs() -> None:
    """The deliverable of section 5.1: not a single number but an answer to
    'what should we change'. A large connectivity cost argues for a different
    lattice, a large quantisation cost for more strut lengths."""
    n = 6
    _, target = distribution(_random_model(n, seed=3, scale=1.3))
    _, loss = design(target, n=n, allowed=_chain(n))

    assert loss.ideal == pytest.approx(0.0, abs=1e-6)
    assert loss.connectivity_cost >= -1e-9
    assert loss.quantisation_cost >= -1e-9
    assert loss.as_dict()["dominant"] in ("connectivity", "quantisation")


def test_an_unconstrained_target_costs_nothing_to_reach() -> None:
    """A target that came from a pairwise model with full connectivity is
    reachable exactly, and a non-zero ideal loss would mean the solver, not the
    constraints, is the problem."""
    n = 5
    _, target = distribution(_random_model(n, seed=5))
    _, loss = design(target, n=n)
    assert loss.ideal < 1e-8
    assert loss.connectivity_cost == pytest.approx(0.0, abs=1e-9)


# ----------------------------------------------------------------- metrics


def test_kl_is_zero_only_for_the_same_distribution() -> None:
    _, p = distribution(_random_model(4, seed=6))
    _, q = distribution(_random_model(4, seed=7))
    assert kl_divergence(p, p) == pytest.approx(0.0, abs=1e-12)
    assert kl_divergence(p, q) > 0.0


def test_kl_is_infinite_when_the_model_forbids_something_observed() -> None:
    """A model that assigns zero probability to a state that happens is not
    slightly wrong; it is refuted, and the number should say so."""
    target = np.array([0.5, 0.5])
    model = np.array([1.0, 0.0])
    assert kl_divergence(target, model) == float("inf")

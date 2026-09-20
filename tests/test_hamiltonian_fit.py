"""Fitting from counts, and the question Stage 2 exists to ask.

The comparison has to work in both directions to mean anything: it must find a
term that is there, and it must not invent one that is not. The second is the
harder requirement and the one that would quietly ruin the headline result.
"""

from __future__ import annotations

import numpy as np
import pytest

from dobladilo.hamiltonian.fit import (
    TermSet,
    bootstrap,
    chain_neighbours,
    compare,
    count_by_umi,
    fields_and_pairs,
    fit,
    nested_models,
)
from dobladilo.hamiltonian.metrics import (
    connected_correlations,
    entropy_miller_madow,
    entropy_plugin,
    kish_effective_size,
    kl_divergence,
)
from dobladilo.hamiltonian.model import all_states, distribution


def _counts_from(theta: np.ndarray, model: TermSet, n: int, depth: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weights = np.exp(model.features(all_states(n)) @ theta)
    return rng.multinomial(depth, weights / weights.sum())


# ------------------------------------------------------------------ fitting


def test_a_known_parameter_set_is_recovered_from_counts() -> None:
    n = 5
    model = TermSet("pairwise", fields_and_pairs(n, chain_neighbours(n)))
    rng = np.random.default_rng(0)
    truth = rng.normal(0, 0.6, model.parameters)
    result = fit(_counts_from(truth, model, n, 4_000_000, seed=1), n=n, model=model)

    assert result.converged
    assert np.abs(result.coefficients - truth).max() < 0.02


def test_bootstrap_intervals_cover_the_truth() -> None:
    """Resampled rather than taken from a Hessian: the likelihood is not
    locally quadratic near the edges of the realisable range, which is where
    the interesting couplings live."""
    n = 4
    model = TermSet("pairwise", fields_and_pairs(n, chain_neighbours(n)))
    rng = np.random.default_rng(2)
    truth = rng.normal(0, 0.5, model.parameters)
    counts = _counts_from(truth, model, n, 200_000, seed=3)

    intervals = bootstrap(counts, n=n, model=model, draws=25, seed=4)
    covered = sum(lo <= t <= hi for t, (lo, hi) in zip(truth, intervals, strict=True))
    assert covered >= model.parameters - 1


# -------------------------------------------------------- model comparison


def test_an_undesigned_three_body_term_is_found() -> None:
    n, K = 5, 0.4
    _, _, m3 = nested_models(n)
    rng = np.random.default_rng(5)
    theta = np.zeros(m3.parameters)
    theta[:n] = rng.normal(0, 0.3, n)
    theta[n : n + (n - 1)] = 0.9
    theta[-3:] = K

    result = compare(_counts_from(theta, m3, n, 500_000, seed=6), n=n)
    assert result.preferred.model.name.startswith("M3")
    assert result.as_dict()["excess_beyond_designed"] is True


def test_no_excess_is_invented_when_the_data_is_as_designed() -> None:
    """The requirement that matters more. A comparison that finds structure in
    a purely pairwise dataset would turn every Stage 2 run into a discovery."""
    n = 5
    m1, _, m3 = nested_models(n)
    rng = np.random.default_rng(7)
    theta = np.zeros(m3.parameters)
    theta[:n] = rng.normal(0, 0.3, n)
    theta[n : n + (n - 1)] = 0.9  # three-body terms left at exactly zero

    result = compare(_counts_from(theta, m3, n, 2_000_000, seed=8), n=n)
    assert result.preferred.model.name == m1.name
    assert result.as_dict()["excess_beyond_designed"] is False


def test_the_models_are_nested() -> None:
    """A likelihood ratio between two models only means anything if one
    contains the other."""
    m1, m2, m3 = nested_models(6)
    assert set(m1.terms) < set(m2.terms) < set(m3.terms)


def test_more_parameters_always_fit_better_which_is_why_bic_exists() -> None:
    n = 4
    counts = _counts_from(
        np.concatenate([np.zeros(n), np.full(n - 1, 0.7)]),
        TermSet("p", fields_and_pairs(n, chain_neighbours(n))),
        n,
        100_000,
        seed=9,
    )
    fits = compare(counts, n=n).fits
    assert fits[0].log_likelihood <= fits[1].log_likelihood + 1e-6
    assert fits[1].log_likelihood <= fits[2].log_likelihood + 1e-6
    assert fits[0].bic < fits[2].bic  # but the penalty prefers the simpler one


# ------------------------------------------------------------------- UMIs


def test_pcr_duplicates_are_counted_once() -> None:
    """Amplification duplicates a molecule an unpredictable number of times, so
    reads overstate depth and every interval from it is too narrow."""
    reads = [((1, -1), "aaa")] * 50 + [((1, -1), "bbb")] * 3 + [((-1, 1), "ccc")]
    counts = count_by_umi(reads)
    assert counts[(1, -1)] == 2
    assert counts[(-1, 1)] == 1
    assert sum(counts.values()) == 3  # not 54


# ---------------------------------------------------------------- metrics


def test_the_plugin_entropy_is_biased_low_and_the_correction_helps() -> None:
    """The document's warning, measured. An underestimated residual entropy at
    Stage 3A would look exactly like the symmetry breaking the experiment is
    trying to rule out."""
    rng = np.random.default_rng(10)
    p = rng.dirichlet(np.ones(128) * 0.7)
    truth = float(-(p * np.log(p)).sum())
    counts = rng.multinomial(512, p)

    naive = entropy_plugin(counts, states_possible=128)
    corrected = entropy_miller_madow(counts, states_possible=128)
    assert naive.nats < truth
    assert abs(corrected.nats - truth) < abs(naive.nats - truth)


def test_an_entropy_names_its_estimator_and_admits_undersampling() -> None:
    """'Entropy = 2.31' is not a result. One that says how it was estimated
    and from how much is one that can be argued with."""
    counts = np.array([5, 3, 0, 0, 1, 0, 0, 0])
    reported = entropy_miller_madow(counts).as_dict()
    assert reported["estimator"] == "Miller-Madow"
    assert reported["states_seen"] == 3
    assert reported["undersampled"] is True


def test_connected_correlations_vanish_without_coupling() -> None:
    """Two strongly biased but independent spins have a large raw correlation
    and no connected one. Only the connected part says anything about coupling."""
    from dobladilo.hamiltonian.model import Ising

    states, probabilities = distribution(Ising(h=np.array([1.5, 1.5]), J=np.zeros((2, 2))))
    raw = np.einsum("s,si,sj->ij", probabilities, states, states)
    connected = connected_correlations(states, probabilities)
    assert abs(raw[0, 1]) > 0.5
    assert abs(connected[0, 1]) < 1e-9


def test_kish_size_falls_when_weights_are_uneven() -> None:
    assert kish_effective_size(np.ones(100)) == pytest.approx(100.0)
    assert kish_effective_size(np.array([97.0, 1.0, 1.0, 1.0])) < 5.0


def test_kl_direction_matters() -> None:
    a = np.array([0.7, 0.3])
    b = np.array([0.4, 0.6])
    assert kl_divergence(a, b) != pytest.approx(kl_divergence(b, a))

"""Fitting a Hamiltonian to observed configurations, and asking if it is enough.

Two jobs. The first is routine: counts in, coefficients out, with intervals.

The second is the one HAMILTONIAN.md calls the core of Stage 2, and it is the
more interesting: **are terms needed that were not designed?** A nearest-
neighbour pairwise model is what the plate was built to realise. If the data
wants next-nearest couplings, or three-body terms, that excess is the finding,
and its magnitude and sign point at a structural cause -- plate flexibility,
shared staples, cooperative folding.

So the model is a **set of terms** rather than a fixed Ising: one-body,
two-body, three-body, all handled the same way. That is the maximum-entropy
framing taken literally, and it makes M1, M2 and M3 three entries in a list
rather than three separate pieces of code that could disagree.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from dobladillo.hamiltonian.model import all_states

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

#: Index tuples: (i,) is a field, (i, j) a coupling, (i, j, k) a three-body term.
Term = tuple[int, ...]


@dataclass(frozen=True)
class TermSet:
    """A model class, as the list of terms it is allowed to use."""

    name: str
    terms: tuple[Term, ...]

    @property
    def parameters(self) -> int:
        return len(self.terms)

    def features(self, states: np.ndarray) -> np.ndarray:
        """The product of spins in each term, for every state: an (S, P) array."""
        return np.stack([states[:, list(term)].prod(axis=1) for term in self.terms], axis=1)


def fields_and_pairs(n: int, pairs: Iterable[tuple[int, int]]) -> tuple[Term, ...]:
    return tuple((i,) for i in range(n)) + tuple(tuple(sorted(p)) for p in pairs)


def chain_neighbours(n: int, *, distance: int = 1) -> list[tuple[int, int]]:
    return [(i, i + distance) for i in range(n - distance)]


def nested_models(n: int) -> list[TermSet]:
    """M1, M2, M3 for a linear chain, as HAMILTONIAN.md section 4 defines them.

    Nested on purpose: each contains the last, so a likelihood ratio between
    them is interpretable and the comparison is about *added* terms rather than
    about two unrelated models.
    """
    m1 = fields_and_pairs(n, chain_neighbours(n, distance=1))
    m2 = m1 + tuple(tuple(sorted(p)) for p in chain_neighbours(n, distance=2))
    m3 = m2 + tuple(t for t in itertools.combinations(range(n), 3) if t[2] - t[0] <= 2)
    return [
        TermSet("M1 nearest-neighbour pairwise", m1),
        TermSet("M2 + next-nearest", m2),
        TermSet("M3 + three-body", m3),
    ]


def count_by_umi(observations: Sequence[tuple[Term, str]]) -> Counter[Term]:
    """Count each original molecule once, using its unique identifier.

    PCR duplicates a molecule an unpredictable number of times, so read counts
    overstate the depth. Every confidence interval computed from an inflated
    depth is too narrow, which turns an amplification artefact into a confident
    wrong answer. Deduplicating by UMI is the whole defence, and it has to
    happen before anything is counted.
    """
    seen: set[str] = set()
    counts: Counter[Term] = Counter()
    for configuration, umi in observations:
        if umi in seen:
            continue
        seen.add(umi)
        counts[configuration] += 1
    return counts


@dataclass(frozen=True)
class TermFit:
    model: TermSet
    coefficients: np.ndarray
    log_likelihood: float
    samples: int
    converged: bool
    intervals: np.ndarray | None = field(default=None)

    @property
    def aic(self) -> float:
        return 2 * self.model.parameters - 2 * self.log_likelihood

    @property
    def bic(self) -> float:
        return self.model.parameters * math.log(self.samples) - 2 * self.log_likelihood

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "model": self.model.name,
            "parameters": self.model.parameters,
            "log_likelihood": round(self.log_likelihood, 3),
            "aic": round(self.aic, 2),
            "bic": round(self.bic, 2),
            "converged": self.converged,
            "coefficients": [round(float(c), 4) for c in self.coefficients],
        }
        if self.intervals is not None:
            out["ci95"] = [[round(float(lo), 4), round(float(hi), 4)] for lo, hi in self.intervals]
        return out


def fit(counts: np.ndarray, *, n: int, model: TermSet) -> TermFit:
    """Maximum likelihood over the model's terms, from counts over all 2^n states."""
    from scipy.optimize import minimize

    states = all_states(n)
    features = model.features(states)
    total = float(counts.sum())
    observed = (counts / total) @ features

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        exponent = features @ theta
        shift = exponent.max()
        weights = np.exp(exponent - shift)
        partition = weights.sum()
        expected = (weights @ features) / partition
        # Negative log-likelihood per observation, and its gradient, which is
        # again just the mismatch between expected and observed statistics.
        value = float(np.log(partition) + shift - observed @ theta)
        return value, expected - observed

    result = minimize(
        objective,
        np.zeros(model.parameters),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 5000, "ftol": 1e-16, "gtol": 1e-9},
    )
    per_observation = -float(result.fun)
    _, gradient = objective(result.x)
    return TermFit(
        model=model,
        coefficients=result.x,
        log_likelihood=per_observation * total,
        samples=int(total),
        converged=bool(np.abs(gradient).max() < 1e-4),
    )


def bootstrap(
    counts: np.ndarray, *, n: int, model: TermSet, draws: int = 40, seed: int = 0
) -> np.ndarray:
    """95% intervals by resampling the observations, not by inverting a Hessian.

    Slower, and it makes no assumption about the likelihood being locally
    quadratic -- which it is not near the edges of the realisable range, where
    the interesting couplings live.
    """
    rng = np.random.default_rng(seed)
    total = int(counts.sum())
    probabilities = counts / counts.sum()
    samples = np.stack(
        [
            fit(rng.multinomial(total, probabilities), n=n, model=model).coefficients
            for _ in range(draws)
        ]
    )
    intervals: np.ndarray = np.percentile(samples, [2.5, 97.5], axis=0).T
    return intervals


@dataclass(frozen=True)
class Comparison:
    fits: tuple[TermFit, ...]

    @property
    def preferred(self) -> TermFit:
        return min(self.fits, key=lambda f: f.bic)

    def as_dict(self) -> dict[str, Any]:
        best = self.preferred
        return {
            "models": [f.as_dict() for f in self.fits],
            "preferred_by_bic": best.model.name,
            "excess_beyond_designed": best.model.name != self.fits[0].model.name,
            "note": (
                "An excess beyond the designed model is the finding, not a nuisance. "
                "Report its magnitude and sign and look for the structural cause."
            ),
        }


def compare(counts: np.ndarray, *, n: int, models: Sequence[TermSet] | None = None) -> Comparison:
    """Fit each nested model and rank them. BIC decides, because it penalises
    parameters harder than AIC, and the claim being made -- that the data needs
    a term nobody designed -- deserves the stricter test."""
    chosen = list(models) if models is not None else nested_models(n)
    return Comparison(tuple(fit(counts, n=n, model=m) for m in chosen))

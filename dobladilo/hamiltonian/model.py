"""The Ising model, with the sign convention written down.

Sign conventions are the classic silent error in this corner of physics: every
formula below is correct under exactly one of them, and the wrong one produces
numbers that look entirely reasonable. So it is stated once, here, and every
other module refers back to it:

    p(s) is proportional to exp( sum_i h_i s_i + sum_{i<j} J_ij s_i s_j )

with s_i in {-1, +1} and everything in units of kT. Positive J favours
agreement between the two spins; positive h favours +1.

The check that this is the right convention is not an assertion. HAMILTONIAN.md
gives the exact two-spin result

    J = (1/4) ln[ p(++) p(--) / p(+-) p(-+) ]

which holds only under this convention, and a test round-trips through it.

Distributions are computed by **enumerating every state**, which is exact and
has no sampling error to confuse with a modelling error. That caps the size:
2^n states, so about 20 spins on a laptop. Past that the honest thing is to
refuse rather than to silently return something approximate, and the extension
is MCMC with its own error bars.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

#: Enumeration is exact but exponential. Above this the caller needs sampling,
#: and should be told so rather than handed a number that took an hour.
MAX_EXACT_SPINS = 22


@dataclass(frozen=True)
class Ising:
    """Fields and couplings, in kT."""

    h: np.ndarray
    J: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.h)
        if self.J.shape != (n, n):
            raise ValueError(f"J is {self.J.shape}, expected ({n}, {n})")
        if not np.allclose(self.J, self.J.T):
            raise ValueError("J must be symmetric: J_ij and J_ji are the same coupling")
        if np.any(np.diag(self.J) != 0):
            raise ValueError("J must have a zero diagonal: a spin does not couple to itself")

    @property
    def n(self) -> int:
        return len(self.h)

    @property
    def couplings(self) -> np.ndarray:
        """The upper-triangle entries, which is what is actually free."""
        return self.J[np.triu_indices(self.n, k=1)]

    def as_dict(self) -> dict[str, Any]:
        return {
            "spins": self.n,
            "h": [round(float(v), 4) for v in self.h],
            "J": [round(float(v), 4) for v in self.couplings],
        }


def all_states(n: int) -> np.ndarray:
    """Every configuration, as a (2^n, n) array of +/-1."""
    if n > MAX_EXACT_SPINS:
        raise ValueError(
            f"{n} spins is {2**n:.3g} states; enumeration is exact but exponential and "
            f"stops being sensible past {MAX_EXACT_SPINS}. Use sampling, and carry its error."
        )
    bits = ((np.arange(2**n)[:, None] >> np.arange(n)) & 1).astype(np.int8)
    return (1 - 2 * bits).astype(np.float64)  # bit 0 -> +1, bit 1 -> -1


def log_weights(model: Ising, states: np.ndarray) -> np.ndarray:
    """The exponent of each state's Boltzmann weight, in kT."""
    field = states @ model.h
    # states @ J @ states, summed over i<j only, which the factor of a half
    # achieves given J is symmetric with a zero diagonal.
    coupling = 0.5 * np.einsum("si,ij,sj->s", states, model.J, states)
    exponent: np.ndarray = field + coupling
    return exponent


def distribution(model: Ising) -> tuple[np.ndarray, np.ndarray]:
    """Every state and its exact probability."""
    states = all_states(model.n)
    weights = log_weights(model, states)
    weights = weights - weights.max()  # subtract the max before exponentiating
    probabilities = np.exp(weights)
    return states, probabilities / probabilities.sum()


def moments(model: Ising) -> tuple[np.ndarray, np.ndarray]:
    """<s_i> and <s_i s_j>: the sufficient statistics of a pairwise model.

    These are what the inverse problem matches. Everything else about the
    distribution follows from them, which is the whole content of the maximum
    entropy argument.
    """
    states, probabilities = distribution(model)
    magnetisation = probabilities @ states
    correlation = np.einsum("s,si,sj->ij", probabilities, states, states)
    np.fill_diagonal(correlation, 1.0)  # s_i^2 is 1 by construction
    return magnetisation, correlation


def empirical_moments(states: np.ndarray, counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The same statistics, from observed configurations and their counts."""
    weights = counts / counts.sum()
    magnetisation = weights @ states
    correlation = np.einsum("s,si,sj->ij", weights, states, states)
    np.fill_diagonal(correlation, 1.0)
    return magnetisation, correlation


def two_spin_coupling(probabilities: dict[tuple[int, int], float]) -> float:
    """J from the four two-spin probabilities, exactly.

    J = (1/4) ln[ p(++) p(--) / p(+-) p(-+) ]

    Exact for a two-spin Ising model, independent of the fields, and the
    measurement HAMILTONIAN.md section 4 uses at Stage 1. Here it serves as an
    independent check on the forward model: a convention error anywhere above
    shows up as a disagreement with this.
    """
    pp = probabilities[(+1, +1)]
    mm = probabilities[(-1, -1)]
    pm = probabilities[(+1, -1)]
    mp = probabilities[(-1, +1)]
    return 0.25 * float(np.log(pp * mm / (pm * mp)))

"""Target distribution in, manufacturable couplings out.

The unconstrained pairwise inverse problem is maximum entropy and convex, and
its gradient is unusually pleasant: the derivative of the log-likelihood with
respect to a parameter is just the mismatch between the data's moment and the
model's. So the solver is gradient ascent on a moment mismatch, and it either
converges or tells you it did not.

The contribution is not that part. It is the **manufacturability constraints**,
which are what makes this different from the textbook problem:

- `J_ij` is realisable only by some available strut length: a discrete,
  bounded set, not the real line;
- `h_i` is quantised, roughly half a kT at a time over about ten;
- connectivity is planar and of limited degree, because the spins sit on a
  plate and a coupling needs a physical strut between neighbours.

Those three degrade the achievable distribution in different ways and for
different reasons, so this module **reports the loss from each separately**.
A single "we got within X" hides whether the answer is to allow more strut
lengths, to make a finer bias ladder, or to change the lattice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from dobladillo.hamiltonian.model import (
    Ising,
    distribution,
    empirical_moments,
    log_weights,
    moments,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Bias ladder: HAMILTONIAN.md section 2.1 gives about +/-10 kT in steps of
#: roughly 0.5, which is four to five bits of weight precision. Thermal noise
#: eats the bottom of that range.
FIELD_STEP_KT = 0.5
FIELD_LIMIT_KT = 10.0

#: Couplings realisable by the mechanical route, section 2.2: 1 to 3 kT, and
#: the sign is set by which latch the strut displaces. A placeholder set until
#: Stage 1 measures what strut lengths actually deliver -- which is the point
#: of Stage 1, and this constant is where that measurement lands.
REALISABLE_COUPLINGS_KT: tuple[float, ...] = (
    -3.0,
    -2.5,
    -2.0,
    -1.5,
    -1.0,
    0.0,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
)


#: A fit whose moments agree this well reproduces the target distribution to
#: far better than any measurement will resolve it.
MOMENT_TOLERANCE = 1e-4


@dataclass(frozen=True)
class Fit:
    model: Ising
    converged: bool
    iterations: int
    moment_error: float
    optimiser_status: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.model.as_dict(),
            "converged": self.converged,
            "iterations": self.iterations,
            "max_moment_error": float(f"{self.moment_error:.3g}"),
            "optimiser_status": self.optimiser_status,
        }


def kl_divergence(target: np.ndarray, model: np.ndarray) -> float:
    """D(target || model), in nats. Zero only when they agree everywhere."""
    mask = target > 0
    if np.any(model[mask] <= 0):
        return float("inf")
    return float(np.sum(target[mask] * np.log(target[mask] / model[mask])))


def solve(
    target: np.ndarray,
    *,
    n: int,
    allowed: np.ndarray | None = None,
    tolerance: float = 1e-8,
    max_iterations: int = 5000,
) -> Fit:
    """Fit (h, J) to a target distribution over all 2^n states.

    Quasi-Newton rather than plain gradient ascent, and the reason is measured
    rather than assumed: with a fixed step the naive version converges in 64
    iterations at 3 spins, needs 2306 at 5, and **fails to converge at all at
    8**, still 0.35 kT out after twenty thousand steps. The programme this
    serves wants 25 to 100 spins. Finding that on synthetic data cost an
    afternoon; finding it on Stage 3 data would have cost a great deal more.

    The gradient is still the pleasant part: the derivative of the
    log-likelihood with respect to any parameter is exactly the mismatch
    between the target's moment and the model's, so there is no separate
    derivation to get wrong.

    `allowed` is a boolean (n, n) mask of which pairs may couple. Pairs outside
    it are never given a parameter, rather than fitted and then discarded: a
    coupling that is fitted and then deleted takes its explanatory work with
    it, and nothing else gets the chance to compensate.
    """
    from scipy.optimize import minimize

    from dobladillo.hamiltonian.model import all_states

    states = all_states(n)
    target_m, target_c = empirical_moments(states, target)

    mask = np.ones((n, n), dtype=bool) if allowed is None else allowed.copy()
    np.fill_diagonal(mask, False)
    if not np.allclose(mask, mask.T):
        raise ValueError("the connectivity mask must be symmetric")
    pairs = np.array(np.triu(mask, k=1).nonzero()).T

    def unpack(x: np.ndarray) -> Ising:
        h = x[:n]
        J = np.zeros((n, n))
        for value, (i, j) in zip(x[n:], pairs, strict=True):
            J[i, j] = J[j, i] = value
        return Ising(h=h, J=J)

    def objective(x: np.ndarray) -> tuple[float, np.ndarray]:
        model = unpack(x)
        model_m, model_c = moments(model)
        # Negative log-likelihood up to a constant: <E> under the target minus
        # log Z. Minimising it is maximising the likelihood.
        log_z = float(
            np.log(np.exp(log_weights(model, states) - log_weights(model, states).max()).sum())
            + log_weights(model, states).max()
        )
        value = (
            log_z
            - float(target_m @ model.h)
            - float(sum(model.J[i, j] * target_c[i, j] for i, j in pairs))
        )
        gradient = np.concatenate(
            [model_m - target_m, np.array([model_c[i, j] - target_c[i, j] for i, j in pairs])]
        )
        return value, gradient

    start = np.zeros(n + len(pairs))
    result = minimize(
        objective,
        start,
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": max_iterations, "ftol": 1e-16, "gtol": tolerance},
    )
    fitted = unpack(result.x)
    model_m, model_c = moments(fitted)
    error = max(
        float(np.abs(model_m - target_m).max()),
        float(max((abs(model_c[i, j] - target_c[i, j]) for i, j in pairs), default=0.0)),
    )
    # Convergence is judged on the moment error, not on the optimiser's own
    # verdict. L-BFGS reports failure when its line search stalls, which it
    # does at n=12 while the moments already agree to 2e-5 -- converged for
    # every purpose this serves. The optimiser's opinion is kept alongside
    # rather than instead.
    return Fit(
        model=fitted,
        converged=error < MOMENT_TOLERANCE,
        iterations=int(result.nit),
        moment_error=error,
        optimiser_status=str(result.message),
    )


def _snap(values: np.ndarray, ladder: Sequence[float] | np.ndarray) -> np.ndarray:
    grid = np.asarray(ladder, dtype=float)
    snapped: np.ndarray = grid[np.abs(values[..., None] - grid).argmin(axis=-1)]
    return snapped


def quantise(
    model: Ising,
    *,
    couplings: Sequence[float] = REALISABLE_COUPLINGS_KT,
    field_step: float = FIELD_STEP_KT,
    field_limit: float = FIELD_LIMIT_KT,
) -> Ising:
    """Snap a fitted model onto what can actually be built."""
    ladder = np.arange(-field_limit, field_limit + field_step / 2, field_step)
    h = _snap(np.clip(model.h, -field_limit, field_limit), ladder)

    J = np.zeros_like(model.J)
    upper = np.triu_indices(model.n, k=1)
    J[upper] = _snap(model.J[upper], couplings)
    return Ising(h=h, J=J + J.T)


@dataclass(frozen=True)
class Decomposition:
    """Where the achievable distribution loses to the target, and to what."""

    ideal: float
    connectivity_limited: float
    quantised: float

    @property
    def connectivity_cost(self) -> float:
        return self.connectivity_limited - self.ideal

    @property
    def quantisation_cost(self) -> float:
        return self.quantised - self.connectivity_limited

    def as_dict(self) -> dict[str, Any]:
        return {
            "kl_ideal": round(self.ideal, 6),
            "kl_connectivity_limited": round(self.connectivity_limited, 6),
            "kl_quantised": round(self.quantised, 6),
            "cost_of_connectivity": round(self.connectivity_cost, 6),
            "cost_of_quantisation": round(self.quantisation_cost, 6),
            "dominant": (
                "connectivity"
                if self.connectivity_cost > self.quantisation_cost
                else "quantisation"
            ),
        }


def design(
    target: np.ndarray, *, n: int, allowed: np.ndarray | None = None, **solver: Any
) -> tuple[Ising, Decomposition]:
    """Solve, constrain, quantise, and say what each step cost.

    Three fits rather than one, because the useful output is not a number but
    an answer to "what should we change": a large connectivity cost argues for
    a different lattice, a large quantisation cost for a finer ladder or more
    strut lengths.
    """
    ideal = solve(target, n=n, **solver)
    limited = ideal if allowed is None else solve(target, n=n, allowed=allowed, **solver)
    built = quantise(limited.model)

    return built, Decomposition(
        ideal=kl_divergence(target, distribution(ideal.model)[1]),
        connectivity_limited=kl_divergence(target, distribution(limited.model)[1]),
        quantised=kl_divergence(target, distribution(built)[1]),
    )

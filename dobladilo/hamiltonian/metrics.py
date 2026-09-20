"""Information measures, and the sampling bias that ruins them quietly.

The headline number of the whole programme is a KL divergence between a target
distribution and a realised one (HAMILTONIAN.md Stage 3B), and Stage 3A turns
on a residual entropy. Both are estimated from counts, and **entropy estimated
from counts is biased downwards**: unseen states contribute nothing, so a
finite sample always looks more ordered than the distribution it came from.

At the sample sizes here -- 10^9 molecules but 2^25 states -- that bias is not
a rounding error. A plug-in estimate of the residual entropy of a frustrated
lattice would come out low and look like the symmetry breaking the experiment
is trying to rule out.

So every estimator here **names itself in its output**. "Entropy = 2.31" is not
a result; "entropy = 2.31 (Miller-Madow, 4096 samples, 61 states seen of 128)"
is one that can be argued with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Entropy:
    """A value, the estimator that produced it, and what it was estimated from."""

    nats: float
    estimator: str
    samples: int
    states_seen: int
    states_possible: int

    @property
    def coverage(self) -> float:
        return self.states_seen / self.states_possible if self.states_possible else 0.0

    #: Observations per observed state, below which the frequencies that go
    #: into an entropy are themselves too noisy to trust.
    MIN_PER_STATE = 10

    @property
    def undersampled(self) -> bool:
        """Is this sample too thin for the estimate to mean much?

        Judged against the states actually SEEN, not the states possible. The
        obvious rule -- fewer samples than states -- is wrong in both
        directions: a sharply peaked distribution never visits most of its
        state space however long you sample, which is structure rather than
        undersampling, while nine observations spread over three states is
        clearly too thin even though nine exceeds eight.

        Reported rather than corrected. No estimator rescues a sample that
        never saw the distribution, and a number that hides it is worse than
        one that admits it.
        """
        return self.samples < self.MIN_PER_STATE * max(self.states_seen, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "nats": round(self.nats, 4),
            "estimator": self.estimator,
            "samples": self.samples,
            "states_seen": self.states_seen,
            "states_possible": self.states_possible,
            "coverage": round(self.coverage, 4),
            "undersampled": self.undersampled,
            "samples_per_state_seen": round(self.samples / max(self.states_seen, 1), 1),
        }


def entropy_plugin(counts: np.ndarray, *, states_possible: int | None = None) -> Entropy:
    """The naive estimate: -sum p log p from observed frequencies.

    Included so the bias can be shown rather than described, and because it is
    the right answer when the sample is large compared with the number of
    states. It is never the right answer when it is not.
    """
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    seen = counts[counts > 0]
    p = seen / total
    return Entropy(
        nats=float(-(p * np.log(p)).sum()),
        estimator="plug-in",
        samples=int(total),
        states_seen=len(seen),
        states_possible=states_possible or len(counts),
    )


def entropy_miller_madow(counts: np.ndarray, *, states_possible: int | None = None) -> Entropy:
    """Plug-in plus the leading bias correction, (K-1)/2N.

    K is the number of states actually *observed*, not the number possible:
    using the latter over-corrects wildly when most states are unseen, which is
    exactly the regime this is for. Cheap, always an improvement on plug-in,
    and not a substitute for an adequate sample.
    """
    base = entropy_plugin(counts, states_possible=states_possible)
    correction = (base.states_seen - 1) / (2.0 * base.samples) if base.samples else 0.0
    return Entropy(
        nats=base.nats + correction,
        estimator="Miller-Madow",
        samples=base.samples,
        states_seen=base.states_seen,
        states_possible=base.states_possible,
    )


def kl_divergence(target: np.ndarray, model: np.ndarray) -> float:
    """D(target || model) in nats. Infinite if the model forbids what happened.

    Not symmetric, and the direction matters: this one asks how badly the model
    fails to cover the target, which is the question for "did we realise the
    distribution we designed".
    """
    target = np.asarray(target, dtype=float)
    model = np.asarray(model, dtype=float)
    mask = target > 0
    if np.any(model[mask] <= 0):
        return float("inf")
    return float(np.sum(target[mask] * np.log(target[mask] / model[mask])))


def connected_correlations(states: np.ndarray, probabilities: np.ndarray) -> np.ndarray:
    """<s_i s_j> - <s_i><s_j>.

    The connected part, because the raw correlation of two strongly biased
    spins is large whether or not they interact. Only the connected part says
    anything about coupling.
    """
    magnetisation = probabilities @ states
    joint = np.einsum("s,si,sj->ij", probabilities, states, states)
    connected: np.ndarray = joint - np.outer(magnetisation, magnetisation)
    return connected


def kish_effective_size(counts: np.ndarray) -> float:
    """How many equally-weighted observations an uneven count vector is worth.

    Kish's measure. It answers "how much does the unevenness of these weights
    cost me in precision", which is a real question when some states dominate.

    It does NOT answer the PCR question. Amplification duplicates molecules, so
    a read count overstates how many independent molecules were seen, and no
    function of the read counts alone can tell you by how much -- that needs
    the UMIs. See `hamiltonian.fit.count_by_umi`.
    """
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    if total <= 0:
        return 0.0
    return float(total**2 / np.square(counts).sum())

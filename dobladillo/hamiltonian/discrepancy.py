"""Designed Hamiltonian in, realised Hamiltonian out.

HAMILTONIAN.md section 1: *"The scientific content is the discrepancy between
the designed and the realised Hamiltonian."* This module is where that
discrepancy is written down as a model, so it can be fitted rather than
lamented -- and, before any data exists, so its consequences can be simulated.

Four terms, each from a different place and each with a different signature:

- **synthesis scatter**: every construct is a slightly different molecule.
  Independent, zero-mean, and the quantity Stage 0's variance decomposition is
  designed to measure.
- **context offset and slope**: origami is not a test tube, so a latch's
  nearest-neighbour prediction is systematically off. Affects all constructs
  the same way, which is what makes it separable from scatter.
- **ligation efficiency bias**: the readout counts one state more readily than
  the other. Section 6.4 warns this is *indistinguishable from a bias field*,
  and §3.3 says it will not be uniform. Simulated here so the damage can be
  seen rather than argued about.
- **surface bias**: only on AFM-measured data, and only in one direction --
  mica flattens, which favours whichever state lies flatter.

Everything is in kT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from dobladillo.hamiltonian.model import Ising, all_states, distribution


@dataclass(frozen=True)
class Noise:
    """What stands between a designed Hamiltonian and the one that exists."""

    #: Construct-to-construct scatter at fixed design, one standard deviation.
    #: Stage 0's go/no-go: above about 1 kT, couplings of 1 to 3 kT are
    #: unresolvable and the mechanical coupling route is dead.
    synthesis_kt: float = 0.3

    #: A constant offset between the nearest-neighbour prediction and what the
    #: origami context delivers. Expected non-zero; measured at Stage 0.
    context_offset_kt: float = 0.0

    #: And a multiplicative distortion of the same map.
    context_slope: float = 1.0

    #: Log-odds by which the readout over-reports the +1 state. A scalar
    #: applies it uniformly across spins; a sequence gives one per spin, which
    #: is what §3.3 says to expect. The distinction turns out to matter a great
    #: deal -- see `LIGATION_NOTE`.
    ligation_bias: float | tuple[float, ...] = 0.0

    #: Surface bias, AFM only, favouring the flatter state.
    surface_kt: float = 0.0

    #: Log-odds by which the readout over-reports molecules whose two spins
    #: AGREE. Unlike the per-spin bias this one does not reduce to a field, and
    #: it is the only form of readout bias that can corrupt a coupling.
    ligation_pair_bias: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "synthesis_kt": self.synthesis_kt,
            "context_offset_kt": self.context_offset_kt,
            "context_slope": self.context_slope,
            "ligation_bias": self.ligation_bias,
            "surface_kt": self.surface_kt,
        }


def realise(designed: Ising, noise: Noise, *, rng: np.random.Generator) -> Ising:
    """One physical instance of a designed Hamiltonian.

    The context terms act on couplings and fields alike, because both are set
    by the same latch chemistry: if origami context shifts a latch's free
    energy, it shifts the bias it sets and the coupling it mediates together.
    Treating them independently would be modelling two errors where there is
    one.
    """
    n = designed.n
    h = noise.context_slope * designed.h + noise.context_offset_kt
    h = h + rng.normal(0.0, noise.synthesis_kt, n)

    upper = np.triu_indices(n, k=1)
    couplings = noise.context_slope * designed.J[upper]
    couplings = couplings + rng.normal(0.0, noise.synthesis_kt, len(couplings))
    J = np.zeros((n, n))
    J[upper] = couplings
    return Ising(h=h + noise.surface_kt, J=J + J.T)


def observe(model: Ising, noise: Noise, depth: int, *, rng: np.random.Generator) -> np.ndarray:
    """Counts as the readout would deliver them, bias included.

    The ligation bias enters here rather than in `realise`, and the distinction
    matters: it is a property of the **measurement**, not of the molecule. A
    fit that does not know about it will absorb it into h and report a bias
    field that is not there.
    """
    states, probabilities = distribution(model)
    bias = np.asarray(noise.ligation_bias, dtype=float)
    if np.any(bias != 0.0):
        # Each spin in its +1 state makes the molecule this much more likely to
        # be counted. Per-spin, because a uniform bias and a per-spin one do
        # very different damage.
        per_spin = np.broadcast_to(bias, (model.n,))
        weights = probabilities * np.exp((states == 1) @ per_spin)
        probabilities = weights / weights.sum()

    if noise.ligation_pair_bias:
        # Depends on the JOINT state, so it cannot be absorbed into fields.
        agree = (states[:, 0] == states[:, 1]).astype(float) if model.n >= 2 else 0.0
        weights = probabilities * np.exp(noise.ligation_pair_bias * agree)
        probabilities = weights / weights.sum()
    return rng.multinomial(depth, probabilities)


#: This refines HAMILTONIAN.md section 6.4, which warns that a state-dependent
#: ligation efficiency "would silently corrupt every fitted parameter". Measured
#: here, and the statement turns out to be sharper than that, in a way that
#: matters for what Stage 1 has to calibrate.
#:
#: A ligation bias that depends on **each spin separately** -- whether uniform
#: across sites or different at every site -- multiplies p(s) by
#: exp(sum_i b_i [s_i = +1]), which is algebraically **identical to a shift in
#: the fields**. Fields do not enter J in a pairwise model, so such a bias
#: corrupts h exactly and leaves J untouched. Simulation agrees: at biases up
#: to 0.6 in log-odds, uniform or differential, the recovered coupling moves by
#: about 0.001 kT.
#:
#: What does corrupt J is a bias that depends on the **joint** state: an
#: efficiency that is different when the two neighbours agree. That cannot be
#: absorbed into fields, and it is indistinguishable from a coupling.
#:
#: The consequence for Stage 1, whose entire decision rests on J: the expensive
#: calibration is not per-site efficiency. It is establishing that efficiency
#: does not depend on the NEIGHBOUR's state. The locked-construct controls of
#: section 3.3 should therefore be locked in all four joint states, not in the
#: two states of one spin.
LIGATION_NOTE = (
    "a per-spin ligation bias is exactly a field shift and cannot corrupt J; "
    "only a joint-state bias can, so calibrate the four joint states"
)


@dataclass(frozen=True)
class Recovery:
    """What came back, against what went in."""

    designed_coupling: float
    recovered_coupling: float
    recovered_field_bias: float
    depth: int
    noise: Noise

    @property
    def coupling_error(self) -> float:
        return abs(self.recovered_coupling - self.designed_coupling)

    def as_dict(self) -> dict[str, Any]:
        return {
            "designed_J": round(self.designed_coupling, 4),
            "recovered_J": round(self.recovered_coupling, 4),
            "coupling_error": round(self.coupling_error, 4),
            "spurious_mean_field": round(self.recovered_field_bias, 4),
            "depth": self.depth,
            "noise": self.noise.as_dict(),
        }


def recover_two_spin(
    coupling_kt: float, noise: Noise, *, depth: int = 1_000_000, seed: int = 0
) -> Recovery:
    """Design a two-spin coupling, realise it, measure it, and fit it back.

    Two spins because that is Stage 1, the decision point of the whole
    programme, and because the coupling has an exact closed form there -- so
    the recovery is not confounded by the solver.
    """
    rng = np.random.default_rng(seed)
    designed = Ising(h=np.zeros(2), J=np.array([[0.0, coupling_kt], [coupling_kt, 0.0]]))
    built = realise(designed, noise, rng=rng)
    counts = observe(built, noise, depth, rng=rng)

    states = all_states(2)
    table = {
        (int(s[0]), int(s[1])): float(c) / counts.sum() for s, c in zip(states, counts, strict=True)
    }
    from dobladillo.hamiltonian.model import two_spin_coupling

    recovered = two_spin_coupling(table)
    # The apparent field, which is where an unmodelled ligation bias lands.
    magnetisation = float((counts / counts.sum()) @ states.mean(axis=1))
    return Recovery(coupling_kt, recovered, magnetisation, depth, noise)


def noise_floor(
    coupling_kt: float = 1.0,
    *,
    levels: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0),
    repeats: int = 40,
    depth: int = 1_000_000,
    tolerance_kt: float = 0.3,
) -> list[dict[str, Any]]:
    """At what synthesis scatter does a coupling of this size stop coming back?

    The third of HAMILTONIAN.md section 7's questions. `tolerance_kt` is taken
    from Stage 1's own go/no-go, which asks that J be constant across the bias
    grid to within about 0.3 kT: a scatter that blurs J by more than that makes
    the stage's criterion unmeetable whatever the sampling depth.
    """
    results = []
    for level in levels:
        noise = Noise(synthesis_kt=level)
        errors = [
            recover_two_spin(coupling_kt, noise, depth=depth, seed=s).coupling_error
            for s in range(repeats)
        ]
        errors_array = np.asarray(errors)
        # A construct so extreme that a state never appears is not a large
        # error, it is an absent measurement. Counted separately rather than
        # dropped, because at high scatter it becomes the dominant outcome and
        # a median over the survivors would look reassuring.
        finite = errors_array[np.isfinite(errors_array)]
        unmeasurable = int((~np.isfinite(errors_array)).sum())
        results.append(
            {
                "synthesis_kt": level,
                "median_error_kt": round(float(np.median(finite)), 4) if finite.size else None,
                "p90_error_kt": (
                    round(float(np.percentile(finite, 90)), 4) if finite.size else None
                ),
                "unmeasurable": unmeasurable,
                "within_tolerance": bool(
                    finite.size == len(errors_array) and np.median(finite) < tolerance_kt
                ),
            }
        )
    return results

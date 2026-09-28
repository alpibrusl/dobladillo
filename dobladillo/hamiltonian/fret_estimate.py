"""From FRET signals to p(latched): the calibration chain, and its self-check.

Written against the synthetic twin (`fret_synthetic`) so it could be proved
right before any sample exists. It is the kernel `hamiltonian/fret.py` will
need, not that module: what E4 still owes is listed at the end.

**The chain**, in the order Hellenkamp et al. (*Nat. Methods* 15, 669 (2018))
and Lee et al. (*Biophys. J.* 88, 2939 (2005)) apply it:

1. background, from blank windows (smFRET) or a buffer well (bulk);
2. leakage alpha = da / dd of donor-only molecules;
3. direct excitation delta = da / aa of acceptor-only molecules;
4. F_DA = da - alpha dd - delta aa, then the proximity ratio
   E_PR = F_DA / (F_DA + dd) and stoichiometry S_PR = (dd + F_DA) /
   (dd + F_DA + aa);
5. gamma and beta from two populations of different E: 1/S_PR is linear in
   E_PR, 1/S_PR = Omega + Sigma E_PR, with gamma = (Omega - 1) /
   (Omega + Sigma - 1) and beta = Omega + Sigma - 1 (Lee 2005);
6. E = F_DA / (F_DA + gamma dd).

**Why gamma matters for p, and when it does not.** Counting single molecules
into two states needs no gamma: a wrong gamma moves both states' E, not
which state a burst is in. A BULK E does need it. Per molecule, F_DA +
gamma dd is the same in either state only when gamma is right, so only then
is the bulk E linear in p and p = (E - E_open) / (E_latched - E_open). With
gamma wrong the relation bends, and p comes out biased everywhere except at
0 and 1 -- which is to say, exactly in the informative window E4 exists to
find. E4 and E5 are bulk.

**How a wrong gamma is detected.** With gamma right, corrected stoichiometry
does not depend on E: the open and latched populations (or the two locked
references, in bulk) have the same S. With it wrong they do not.
`stoichiometry_gap` is that difference, and the estimate says so when it is
too large to be noise. Fitting gamma from the same two populations makes the
gap zero by construction, so the check bites on a gamma supplied from
elsewhere; see MAX_STOICHIOMETRY_GAP for what it can and cannot see.

**What E4 still owes on top of this** (not built here on purpose):
the field and offset from p per rung; error propagated into kT; the gate
verdict and its record in an experiment folder; temperature and magnesium as
recorded conditions of real reads; incomplete labelling in bulk; and a reader
for whatever file the plate reader writes. `experiments/protocols/
e4_dryrun.py` does the first three on synthetic data, as a dry run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from dobladillo.hamiltonian.fret_synthetic import Signals, SyntheticBursts, SyntheticPlate

#: Raw stoichiometry above which a burst has no acceptor, and below which no
#: donor. ALEX sorts species on S (Kapanidis 2004); doubly labelled molecules
#: sit near 0.5 raw and away from both edges.
DONOR_ONLY_ABOVE: Final = 0.8
ACCEPTOR_ONLY_BELOW: Final = 0.2

#: Bursts with fewer photons than this, after background, are too noisy to
#: place in E or S. A standard burst-search cut -- but WHICH photons it counts
#: matters; see `estimate_bursts`.
MIN_PHOTONS: Final = 30.0

#: A stoichiometry gap between the two states larger than this says a
#: SUPPLIED gamma is wrong. Measured on the twin: with gamma right, the gap is
#: 0.001 (3000 bursts) to 0.002 (bulk, three reads); with gamma 20% off it is
#: 0.021-0.023, and bulk p at 0.5 is then 0.025 out. A gamma 10% off stays
#: under the threshold, and biases bulk p by 0.01. When gamma is FITTED from
#: two populations the gap is zero by construction, so the check guards a
#: gamma brought in from elsewhere -- a previous session, a catalogue value.
MAX_STOICHIOMETRY_GAP: Final = 0.02


@dataclass(frozen=True)
class Corrections:
    background: tuple[float, float, float]
    leakage: float
    direct_excitation: float
    gamma: float
    beta: float
    #: Whether gamma and beta were fitted here, or supplied.
    fitted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "background": [round(b, 3) for b in self.background],
            "leakage": round(self.leakage, 4),
            "direct_excitation": round(self.direct_excitation, 4),
            "gamma": round(self.gamma, 4),
            "beta": round(self.beta, 4),
            "gamma_fitted": self.fitted,
        }


@dataclass(frozen=True)
class FretEstimate:
    """p(latched), the two states' E, and whether the calibration held together."""

    p_latched: float
    p_stderr: float
    e_open: float
    e_latched: float
    stoichiometry_open: float
    stoichiometry_latched: float
    corrections: Corrections
    n: int

    @property
    def stoichiometry_gap(self) -> float:
        return abs(self.stoichiometry_latched - self.stoichiometry_open)

    @property
    def gamma_consistent(self) -> bool:
        return self.stoichiometry_gap <= MAX_STOICHIOMETRY_GAP

    def as_dict(self) -> dict[str, Any]:
        return {
            "p_latched": round(self.p_latched, 4),
            "p_stderr": round(self.p_stderr, 4),
            "e_open": round(self.e_open, 4),
            "e_latched": round(self.e_latched, 4),
            "stoichiometry_gap": round(self.stoichiometry_gap, 4),
            "gamma_consistent": self.gamma_consistent,
            "corrections": self.corrections.as_dict(),
            "n": self.n,
        }


def _subtract(s: Signals, bg: tuple[float, float, float]) -> tuple[np.ndarray, ...]:
    return s.dd - bg[0], s.da - bg[1], s.aa - bg[2]


def proximity(dd: Any, da: Any, aa: Any, leakage: float, direct: float) -> tuple[Any, Any, Any]:
    """(F_DA, E_PR, S_PR) from background-subtracted signals: arrays, or their sums."""
    f = da - leakage * dd - direct * aa
    e_pr = f / (f + dd)
    s_pr = (dd + f) / (dd + f + aa)
    return f, e_pr, s_pr


def gamma_beta(points: list[tuple[float, float]]) -> tuple[float, float]:
    """gamma and beta from (E_PR, S_PR) of populations with different E (Lee 2005)."""
    if len(points) < 2:
        raise ValueError("gamma needs at least two populations of different E")
    e = np.array([p[0] for p in points])
    inv_s = np.array([1.0 / p[1] for p in points])
    if np.ptp(e) < 0.1:
        raise ValueError("the populations' E are too close to fit gamma")
    sigma, omega = np.polyfit(e, inv_s, 1)
    beta = omega + sigma - 1.0
    return float((omega - 1.0) / beta), float(beta)


def corrected_e(f: np.ndarray, dd: np.ndarray, gamma: float) -> np.ndarray:
    return f / (f + gamma * dd)


def corrected_s(f: np.ndarray, dd: np.ndarray, aa: np.ndarray, gamma: float, beta: float) -> Any:
    return (gamma * dd + f) / (gamma * dd + f + aa / beta)


def _two_gaussians(
    x: np.ndarray, *, iterations: int = 200
) -> tuple[float, float, float, np.ndarray]:
    """EM for a two-component 1-D Gaussian mixture.

    Returns (weight of the upper component, lower mean, upper mean,
    responsibility of the upper component per point). Started from the
    quartiles, so it is deterministic.
    """
    lo, hi = np.quantile(x, [0.25, 0.75])
    w, s_lo, s_hi = 0.5, np.std(x) / 2 + 1e-6, np.std(x) / 2 + 1e-6
    r = np.full(len(x), 0.5)
    for _ in range(iterations):
        a = (1 - w) * np.exp(-0.5 * ((x - lo) / s_lo) ** 2) / s_lo
        b = w * np.exp(-0.5 * ((x - hi) / s_hi) ** 2) / s_hi
        r = b / np.maximum(a + b, 1e-300)
        w_new = float(r.mean())
        if w_new in (0.0, 1.0):
            break
        lo = float(((1 - r) * x).sum() / (1 - r).sum())
        hi = float((r * x).sum() / r.sum())
        s_lo = float(np.sqrt(((1 - r) * (x - lo) ** 2).sum() / (1 - r).sum())) + 1e-6
        s_hi = float(np.sqrt((r * (x - hi) ** 2).sum() / r.sum())) + 1e-6
        if abs(w_new - w) < 1e-9:
            w = w_new
            break
        w = w_new
    return w, float(lo), float(hi), r


def estimate_bursts(
    data: SyntheticBursts,
    *,
    gamma: float | None = None,
    beta: float | None = None,
    bootstrap: int = 100,
    seed: int = 0,
) -> FretEstimate:
    """p(latched) and E per state from single-molecule bursts.

    Everything is measured from the data: background from blank windows,
    alpha and delta from the incompletely labelled molecules every sample
    has, gamma and beta from the two states themselves. Pass `gamma` (and
    `beta`) to use a calibration from elsewhere instead -- and to see what a
    wrong one does. Only `data.bursts` and `data.blank` are read; the truth is
    not.
    """
    bg = (float(data.blank.dd.mean()), float(data.blank.da.mean()), float(data.blank.aa.mean()))
    dd, da, aa = _subtract(data.bursts, bg)
    raw_s = (dd + da) / np.maximum(dd + da + aa, 1e-9)
    donor_only = ((dd + da) >= MIN_PHOTONS) & (raw_s > DONOR_ONLY_ABOVE)
    acceptor_only = (aa >= MIN_PHOTONS) & (raw_s < ACCEPTOR_ONLY_BELOW)
    # Doubly labelled bursts are selected on ACCEPTOR-excitation photons, which
    # do not depend on the state. Selecting on donor-excitation photons, the
    # obvious choice, is biased: under donor excitation a molecule gives
    # dd + da ~ B (1 - E + gamma E), so with gamma < 1 the latched state is
    # dimmer, loses more bursts to the cut, and p comes out low. On the twin
    # that was 0.285 for a true 0.30 -- twice the bootstrap error.
    fret = (aa >= MIN_PHOTONS) & (raw_s >= ACCEPTOR_ONLY_BELOW) & (raw_s <= DONOR_ONLY_ABOVE)
    if donor_only.sum() < 20 or acceptor_only.sum() < 20:
        raise ValueError("too few donor-only or acceptor-only bursts to calibrate leakage")

    leakage = float(da[donor_only].sum() / dd[donor_only].sum())
    direct = float(da[acceptor_only].sum() / aa[acceptor_only].sum())
    _, e_pr, _ = proximity(dd[fret], da[fret], aa[fret], leakage, direct)

    # The latched state is the high-E one: the pair sits across the joint, and
    # latching brings the arms, and so the dyes, together.
    weight, _, _, upper = _two_gaussians(e_pr)
    latched = upper > 0.5

    def population(mask: np.ndarray) -> tuple[float, float]:
        _, e, s = proximity(
            dd[fret][mask].sum(), da[fret][mask].sum(), aa[fret][mask].sum(), leakage, direct
        )
        return float(e), float(s)

    fitted = gamma is None
    if gamma is None:
        gamma, beta = gamma_beta([population(~latched), population(latched)])
    beta = 1.0 if beta is None else beta

    def state(mask: np.ndarray) -> tuple[float, float]:
        sums = [x[fret][mask].sum() for x in (dd, da, aa)]
        fs = sums[1] - leakage * sums[0] - direct * sums[2]
        return (
            float(corrected_e(np.asarray(fs), np.asarray(sums[0]), gamma)),
            float(
                corrected_s(np.asarray(fs), np.asarray(sums[0]), np.asarray(sums[2]), gamma, beta)
            ),
        )

    e_open, s_open = state(~latched)
    e_latched, s_latched = state(latched)

    rng = np.random.default_rng(seed)
    n = int(fret.sum())
    resampled = [
        _two_gaussians(e_pr[rng.integers(0, n, n)], iterations=100)[0] for _ in range(bootstrap)
    ]
    return FretEstimate(
        p_latched=weight,
        p_stderr=float(np.std(resampled)) if bootstrap else float("nan"),
        e_open=e_open,
        e_latched=e_latched,
        stoichiometry_open=s_open,
        stoichiometry_latched=s_latched,
        corrections=Corrections(bg, leakage, direct, float(gamma), float(beta), fitted),
        n=n,
    )


def estimate_plate(
    plate: SyntheticPlate, *, gamma: float | None = None, beta: float | None = None
) -> dict[str, FretEstimate]:
    """p(latched) for every sample well of a bulk plate.

    Calibration from the control wells: background from `blank`, alpha from
    `donor_only`, delta from `acceptor_only`, and gamma, beta, E_open and
    E_latched from the two locked references. Then, per sample,
    p = (E - E_open) / (E_latched - E_open), which is exact only when gamma is
    right. `p_stderr` is the spread of p across replicate reads, each read
    index taken as one pass through the plate.
    """
    from dobladillo.hamiltonian.fret_synthetic import CONTROL_WELLS

    wells = plate.wells
    missing = [w for w in CONTROL_WELLS if w not in wells]
    if missing:
        raise ValueError(f"a bulk estimate needs the control wells {missing}")
    bg = tuple(float(x.mean()) for x in (wells["blank"].dd, wells["blank"].da, wells["blank"].aa))
    background: tuple[float, float, float] = (bg[0], bg[1], bg[2])

    def means(name: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        dd, da, aa = _subtract(wells[name], background)
        return dd, da, aa

    d_dd, d_da, _ = means("donor_only")
    leakage = float(d_da.mean() / d_dd.mean())
    _, a_da, a_aa = means("acceptor_only")
    direct = float(a_da.mean() / a_aa.mean())

    refs = {}
    for name in ("locked_open", "locked_latched"):
        dd, da, aa = (x.mean() for x in means(name))
        _, e_pr, s_pr = proximity(dd, da, aa, leakage, direct)
        refs[name] = (float(e_pr), float(s_pr))
    fitted = gamma is None
    if gamma is None:
        gamma, beta = gamma_beta([refs["locked_open"], refs["locked_latched"]])
    beta = 1.0 if beta is None else beta

    def e_and_s(name: str) -> tuple[np.ndarray, np.ndarray]:
        dd, da, aa = means(name)
        f = da - leakage * dd - direct * aa
        return corrected_e(f, dd, gamma), corrected_s(f, dd, aa, gamma, beta)

    e_open_reads, s_open_reads = e_and_s("locked_open")
    e_latched_reads, s_latched_reads = e_and_s("locked_latched")
    e_open, e_latched = float(e_open_reads.mean()), float(e_latched_reads.mean())
    corrections = Corrections(background, leakage, direct, float(gamma), float(beta), fitted)

    out = {}
    for name in wells:
        if name in CONTROL_WELLS:
            continue
        e_reads, _ = e_and_s(name)
        p_reads = (e_reads - e_open_reads) / (e_latched_reads - e_open_reads)
        out[name] = FretEstimate(
            p_latched=float((e_reads.mean() - e_open) / (e_latched - e_open)),
            p_stderr=float(np.std(p_reads, ddof=1) / np.sqrt(len(p_reads)))
            if len(p_reads) > 1
            else float("nan"),
            e_open=e_open,
            e_latched=e_latched,
            stoichiometry_open=float(s_open_reads.mean()),
            stoichiometry_latched=float(s_latched_reads.mean()),
            corrections=corrections,
            n=len(e_reads),
        )
    return out

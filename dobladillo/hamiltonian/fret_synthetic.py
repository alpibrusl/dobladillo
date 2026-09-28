"""Synthetic FRET data of known contents, for the stages that read a hinge by FRET (#15).

AFM has a twin (`imaging.synthetic`): scans whose contents are known, with the
bow, drift and streaks a real instrument adds. It found a plane-fit bug and
let E1 and E2 run end to end before any sample existed. E4 and E5 read the
hinge by FRET and had nothing of the kind; this is it. Whatever `hamiltonian/
fret.py` becomes, it is graded here first, against a p(latched) that is known
because it was put in.

**What is simulated.** A two-state hinge -- open or latched -- with a donor
and an acceptor across its joint, so the two states have different transfer
efficiencies E. The instrument is modelled as alternating-excitation FRET
(ALEX; Kapanidis et al., *PNAS* 101, 8936 (2004)), because that is the scheme
in which every correction the calibration needs can be measured rather than
assumed. Three signals per observation:

- `dd`: donor excitation, donor emission;
- `da`: donor excitation, acceptor emission -- sensitised emission plus
  donor LEAKAGE into the acceptor channel (alpha) plus DIRECT EXCITATION of
  the acceptor by the donor laser (delta, relative to `aa`);
- `aa`: acceptor excitation, acceptor emission.

The GAMMA factor is the ratio of the acceptor's to the donor's detected
brightness; with it, E = F_DA / (F_DA + gamma * dd) where F_DA is `da` with
leakage and direct excitation removed. BETA normalises acceptor to donor
excitation. Definitions and correction order are those of Hellenkamp et al.,
*Nat. Methods* 15, 669 (2018), the multi-laboratory smFRET benchmark, and
Lee et al., *Biophys. J.* 88, 2939 (2005). Background is added per channel.

**Two readouts, one model.** E4 and E5 are *bulk* measurements on a
fluorimeter or plate reader (`docs/STAGES_0_AND_1.md`); E6 is two-colour
smFRET. So the same molecules can be rendered either way:

- `synthetic_bursts` -- one row per single-molecule burst, with Poisson photon
  noise, a spread of burst brightness, static heterogeneity in E, and
  incompletely labelled molecules (donor-only, acceptor-only), plus blank
  windows for the background. This is the per-molecule data an smFRET
  instrument records;
- `synthetic_plate` -- bulk wells: the ensemble sum of the same signals with
  read noise, for the sample, the controls calibration needs (donor-only,
  acceptor-only, a buffer blank) and two locked references (open, latched).
  **The references are a requirement this twin exposes, not a convenience:**
  a bulk E is a population average, and without the E of each pure state it
  does not determine p. Whether E4's order includes locked references is
  for its plan to settle.

**What is not simulated**, so nobody mistakes the twin for the instrument:
hinge flipping during a burst (states are static per molecule), photophysics
(blinking, bleaching within a burst), the dependence of E on dye orientation,
and inner-filter effects in bulk. The values in `Calibration` are knobs of the
order reported in Hellenkamp 2018, not measurements of any instrument.

Every generator takes a seed and is deterministic in it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Final

import numpy as np

from dobladillo.hamiltonian.bracket import DESIGN_MAGNESIUM_M, DESIGN_TEMPERATURE_K


@dataclass(frozen=True)
class Calibration:
    """The instrument's corrections. Knobs, of the order reported in Hellenkamp 2018."""

    #: Acceptor-to-donor detected brightness ratio (quantum yield x detection).
    gamma: float = 0.75
    #: Acceptor excitation normalisation; S = 0.5 for a 1:1 labelled molecule.
    beta: float = 1.1
    #: Fraction of donor emission detected in the acceptor channel.
    leakage: float = 0.08
    #: Acceptor directly excited by the donor laser, as a fraction of `aa`.
    direct_excitation: float = 0.06
    #: Mean background counts per burst window, or per bulk read, per channel:
    #: (dd, da, aa).
    background: tuple[float, float, float] = (1.5, 1.0, 0.8)


@dataclass(frozen=True)
class Signals:
    """The three ALEX channels, one entry per observation (burst, window or read)."""

    dd: np.ndarray
    da: np.ndarray
    aa: np.ndarray

    def __len__(self) -> int:
        return len(self.dd)

    def select(self, mask: np.ndarray) -> Signals:
        return Signals(self.dd[mask], self.da[mask], self.aa[mask])


#: Species labels in `FretTruth.species`.
SPECIES: Final = ("open", "latched", "donor_only", "acceptor_only")


@dataclass(frozen=True)
class FretTruth:
    """What was put in. Kept apart from the signals so an estimator cannot peek."""

    p_latched: float
    e_open: float
    e_latched: float
    calibration: Calibration
    #: One label per burst, from SPECIES; empty for bulk data.
    species: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out.pop("species")
        return out


def _conditions(seed: int) -> dict[str, Any]:
    """AGENTS.md rule 5: conditions travel with numbers, synthetic ones too."""
    return {
        "synthetic": True,
        "seed": seed,
        "temperature_k": DESIGN_TEMPERATURE_K,
        "magnesium_m": DESIGN_MAGNESIUM_M,
        "generator": "dobladillo.hamiltonian.fret_synthetic",
    }


@dataclass(frozen=True)
class SyntheticBursts:
    """A single-molecule measurement: bursts, blank windows, and the truth."""

    bursts: Signals
    blank: Signals
    truth: FretTruth
    conditions: dict[str, Any] = field(default_factory=dict)


def expected_signals(
    e: np.ndarray,
    brightness: np.ndarray,
    c: Calibration,
    *,
    donor: np.ndarray,
    acceptor: np.ndarray,
) -> Signals:
    """Mean photon counts per channel for each molecule, before noise and background.

    `brightness` is the donor photons a molecule would give with no transfer.
    With transfer efficiency E, the donor channel gets brightness * (1 - E)
    and sensitised acceptor emission is gamma * brightness * E -- which is
    what makes F_DA / (F_DA + gamma * dd) equal E. Acceptor excitation gives
    beta * gamma * brightness, so the corrected stoichiometry of a doubly
    labelled molecule is exactly 1/2. A molecule without an acceptor has no
    transfer and no `aa`; one without a donor has only `aa` and the direct
    excitation it causes.
    """
    e = np.where(acceptor & donor, e, 0.0)
    dd = np.where(donor, brightness * (1.0 - e), 0.0)
    sensitised = c.gamma * brightness * e
    aa = np.where(acceptor, c.beta * c.gamma * brightness, 0.0)
    da = sensitised + c.leakage * dd + c.direct_excitation * aa
    return Signals(dd, da, aa)


def synthetic_bursts(
    *,
    seed: int,
    p_latched: float,
    e_open: float = 0.25,
    e_latched: float = 0.75,
    n_bursts: int = 4000,
    calibration: Calibration | None = None,
    mean_brightness: float = 80.0,
    e_spread: float = 0.03,
    donor_only_fraction: float = 0.10,
    acceptor_only_fraction: float = 0.08,
    n_blank: int = 2000,
) -> SyntheticBursts:
    """Bursts from a two-state hinge with a known p(latched).

    Burst brightness is log-normal (width 0.5), which gives the long tail of
    bright bursts a real confocal measurement has; `e_spread` is static
    molecule-to-molecule heterogeneity in E, on top of shot noise.
    """
    if not 0.0 <= p_latched <= 1.0:
        raise ValueError(f"p_latched must be in [0, 1], got {p_latched}")
    c = calibration or Calibration()
    rng = np.random.default_rng(seed)

    kind = rng.choice(
        4,
        size=n_bursts,
        p=[
            (1 - p_latched) * (1 - donor_only_fraction - acceptor_only_fraction),
            p_latched * (1 - donor_only_fraction - acceptor_only_fraction),
            donor_only_fraction,
            acceptor_only_fraction,
        ],
    )
    donor = kind != 3
    acceptor = kind != 2
    e = np.where(kind == 1, e_latched, e_open) + rng.normal(0.0, e_spread, n_bursts)
    e = np.clip(e, 0.0, 1.0)
    brightness = mean_brightness * rng.lognormal(-0.125, 0.5, n_bursts)
    mean = expected_signals(e, brightness, c, donor=donor, acceptor=acceptor)
    bg = c.background
    bursts = Signals(
        rng.poisson(mean.dd + bg[0]).astype(float),
        rng.poisson(mean.da + bg[1]).astype(float),
        rng.poisson(mean.aa + bg[2]).astype(float),
    )
    blank = Signals(
        rng.poisson(bg[0], n_blank).astype(float),
        rng.poisson(bg[1], n_blank).astype(float),
        rng.poisson(bg[2], n_blank).astype(float),
    )
    return SyntheticBursts(
        bursts=bursts,
        blank=blank,
        truth=FretTruth(
            p_latched=p_latched,
            e_open=e_open,
            e_latched=e_latched,
            calibration=c,
            species=tuple(SPECIES[k] for k in kind),
        ),
        conditions=_conditions(seed),
    )


#: The wells a bulk calibration needs, besides the samples themselves.
CONTROL_WELLS: Final = ("blank", "donor_only", "acceptor_only", "locked_open", "locked_latched")


@dataclass(frozen=True)
class SyntheticPlate:
    """A bulk measurement: replicate reads per well, and what each sample held.

    `wells[name]` is a `Signals` of replicate reads. Sample wells are named by
    the caller; the controls in CONTROL_WELLS are always present.
    """

    wells: dict[str, Signals]
    truth: dict[str, FretTruth]
    conditions: dict[str, Any] = field(default_factory=dict)


def _bulk_well(
    rng: np.random.Generator,
    *,
    p_latched: float,
    e_open: float,
    e_latched: float,
    c: Calibration,
    donor: bool,
    acceptor: bool,
    signal: float,
    read_noise: float,
    replicates: int,
) -> Signals:
    """Replicate reads of one well: the ensemble mean, background, read noise.

    A well holds ~1e10 molecules, so counting noise is negligible and the
    fraction latched IS p. What varies between reads is the instrument:
    `read_noise` is relative, per channel, per read.
    """
    fractions = np.array([1.0 - p_latched, p_latched])
    e = np.array([e_open, e_latched])
    one = np.ones(2, dtype=bool)
    per_state = expected_signals(
        e, np.full(2, signal), c, donor=one & donor, acceptor=one & acceptor
    )
    bg = c.background
    out = []
    for channel, mean_bg in zip((per_state.dd, per_state.da, per_state.aa), bg, strict=True):
        level = float(fractions @ channel) + mean_bg
        out.append(level * (1.0 + rng.normal(0.0, read_noise, replicates)))
    return Signals(*out)


def synthetic_plate(
    *,
    seed: int,
    samples: dict[str, float],
    e_open: float = 0.25,
    e_latched: float = 0.75,
    calibration: Calibration | None = None,
    signal: float = 1.0e4,
    read_noise: float = 0.003,
    replicates: int = 3,
) -> SyntheticPlate:
    """Bulk reads of samples with known p(latched), plus every control well.

    `samples` maps a well name to its p(latched). All wells share one core
    and one FRET pair -- E4's premise -- so they share E_open and E_latched,
    and the locked references are simply p = 0 and p = 1 of the same core.
    Labelling is taken as complete in bulk; see the module docstring.
    """
    clash = set(samples) & set(CONTROL_WELLS)
    if clash:
        raise ValueError(f"sample names clash with control wells: {sorted(clash)}")
    c = calibration or Calibration()
    rng = np.random.default_rng(seed)

    def well(p: float, *, donor: bool = True, acceptor: bool = True) -> Signals:
        return _bulk_well(
            rng,
            p_latched=p,
            e_open=e_open,
            e_latched=e_latched,
            c=c,
            donor=donor,
            acceptor=acceptor,
            signal=signal,
            read_noise=read_noise,
            replicates=replicates,
        )

    wells = {
        "blank": well(0.0, donor=False, acceptor=False),
        "donor_only": well(0.0, acceptor=False),
        "acceptor_only": well(0.0, donor=False),
        "locked_open": well(0.0),
        "locked_latched": well(1.0),
    }
    truth = {
        name: FretTruth(p_latched=p, e_open=e_open, e_latched=e_latched, calibration=c)
        for name, p in (("locked_open", 0.0), ("locked_latched", 1.0))
    }
    for name, p in samples.items():
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"{name}: p_latched must be in [0, 1], got {p}")
        wells[name] = well(p)
        truth[name] = FretTruth(p_latched=p, e_open=e_open, e_latched=e_latched, calibration=c)
    return SyntheticPlate(wells=wells, truth=truth, conditions=_conditions(seed))

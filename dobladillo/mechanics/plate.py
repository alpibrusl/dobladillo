"""How wrong a half-space fit is on a plate this thin, and by exactly how much.

An AFM indentation curve is routinely converted to a Young's modulus with the
Hertz model, which assumes the sample is an elastic half-space. A DNA origami
plate on mica is not a half-space: it is 2 to 6 nm of soft material bonded to
something rigid. The substrate carries load the half-space would have let the
sample absorb, so the measured force is higher than Hertz predicts, and a Hertz
fit therefore reports a modulus that is too large.

The size of that error is set by the thin-film parameter

    chi = sqrt(R * delta) / h

for tip radius R, indentation depth delta and film thickness h. At chi << 1 the
contact is small compared with the film and Hertz is fine; at chi >> 1 the film
is squeezed flat and Chadwick's asymptotic applies. A single-layer origami
plate under an ordinary imaging tip sits at chi ~ 1, which is the awkward middle
where neither limit holds and the finite-element solve is the only honest
answer.

The useful property of the correction is that it is *exactly independent of the
sample modulus*: every model here is linear elastic, so force scales with E and
the ratio does not. The factor is pure geometry. That is what makes a plate of
designed thickness a calibration object -- its correction factor is known
before anyone measures its stiffness, and it stays known whatever that
stiffness turns out to be.

`nanoindent` does the mechanics. This module decides which plate is being
indented and hands it over; see `NANOINDENT_NOTE`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

from dobladillo.constants import HELIX_DIAMETER_NM

#: Thickness added by one stacked helix layer, nm. A plate's helices lie in the
#: surface plane, so the out-of-plane extent of one layer is the bare helix
#: diameter; interhelix spacing widens the plate, not thickens it.
LAYER_THICKNESS_NM: Final = HELIX_DIAMETER_NM

#: Modulus used internally when asking nanoindent for a correction factor. The
#: factor is exactly modulus-independent -- verified to five digits at 100, 300
#: and 900 MPa -- so this value cannot influence a reported result. It exists
#: only because the solver needs some number to scale its forces by.
_PROBE_MODULUS_MPA: Final = 300.0

#: Poisson's ratio. Hydrated DNA is conventionally taken as incompressible,
#: which forces the mixed (Taylor-Hood) formulation; the single-field one locks
#: at nu = 0.5 and over-stiffens.
_POISSON: Final = 0.5

NANOINDENT_NOTE: Final = """\
Contact mechanics come from LorenaRedondo/nanoindent, which is not on a package index
and therefore an optional extra here (`pip install -e '.[mechanics]'` will not
reach it; install nanoindent from its own checkout). Without it this module
still reports thickness, the thin-film parameter and the regime, because those
are geometry; it cannot report forces or correction factors, because those are
mechanics and mechanics is not this project's job."""

Regime = Literal["half-space", "closed-form", "finite-element"]

#: Boundaries in chi, named for the model they license rather than for the
#: state of the film, because which model may be used is the actual question.
#: Both are measured, not assumed, against the finite-element solve:
#: the bottom effect falls below 5% only at chi ~ 0.04 (h ~ 50 nm for a 10 nm
#: tip at 0.4 nm depth), and the two closed-form corrections disagree with each
#: other by 1% at chi = 0.17, 4% at 0.33, 8% at 0.50 and 31% at 1.00. No
#: origami plate reaches the first boundary: the thickest in `thickness_ladder`
#: is 12 nm and still inflates a Hertz fit by 23%.
_HALF_SPACE_BELOW: Final = 0.05
_CLOSED_FORM_BELOW: Final = 0.5


@dataclass(frozen=True)
class Plate:
    """A folded plate, as the AFM will meet it: a thickness on a rigid floor."""

    layers: int
    """Stacked helix layers. 1 for a flat single-layer origami."""

    footprint_nm: float
    """Longest in-plane dimension, nm. Bounds the simulation domain only."""

    name: str = ""

    def __post_init__(self) -> None:
        if self.layers < 1:
            raise ValueError(f"a plate has at least one layer, got {self.layers}")
        if self.footprint_nm <= 0:
            raise ValueError(f"footprint must be positive, got {self.footprint_nm}")

    @property
    def thickness_nm(self) -> float:
        return self.layers * LAYER_THICKNESS_NM


@dataclass(frozen=True)
class Tip:
    """The indenter, as the force curve depends on it."""

    radius_nm: float
    """Apex radius. A sharp imaging tip is 2 to 10 nm; an MSNL is about 20."""

    depth_nm: float
    """Indentation depth to report at. Keep it well under the plate thickness:
    past roughly a fifth, the linear-elastic small-strain model this rests on
    stops describing what is happening to the duplexes."""

    def __post_init__(self) -> None:
        if self.radius_nm <= 0:
            raise ValueError(f"tip radius must be positive, got {self.radius_nm}")
        if self.depth_nm <= 0:
            raise ValueError(f"indentation depth must be positive, got {self.depth_nm}")


def thin_film_parameter(plate: Plate, tip: Tip) -> float:
    """chi = sqrt(R*delta)/h -- contact size measured in film thicknesses."""
    return float((tip.radius_nm * tip.depth_nm) ** 0.5 / plate.thickness_nm)


def regime(chi: float) -> Regime:
    """Which model the geometry licenses. See the module docstring."""
    if chi < _HALF_SPACE_BELOW:
        return "half-space"
    if chi < _CLOSED_FORM_BELOW:
        return "closed-form"
    return "finite-element"


@dataclass(frozen=True)
class Correction:
    """What a Hertz fit would get wrong, and how confidently we can say so."""

    plate: Plate
    tip: Tip
    chi: float
    hertz_pn: float
    fe_pn: float
    dimitriadis_pn: float
    bec_pn: float

    @property
    def factor(self) -> float:
        """Ratio by which a Hertz fit inflates the modulus *at this depth*.

        Geometry only -- it does not depend on the sample modulus. It does
        depend on depth, and strongly: on a single-layer plate the factor runs
        2.14, 3.12, 4.14, 5.06, 6.10 as the indentation goes 0.1 to 0.5 nm.
        Hertz rises as delta^1.5 and a confined film rises faster, so the two
        curves have different shapes and no single ratio describes them. This
        is why a plate this thin has no well-defined "Hertz modulus" at all
        unless the depth is quoted with it, and why the honest deliverable is
        the force curve rather than a modulus.
        """
        return self.fe_pn / self.hertz_pn

    @property
    def closed_form_spread(self) -> float:
        """Disagreement between the two closed-form corrections, as a fraction
        of the finite-element answer. Large means the closed forms are being
        used outside their range and the solve is doing real work."""
        return abs(self.bec_pn - self.dimitriadis_pn) / self.fe_pn

    def summary(self) -> str:
        name = self.plate.name or f"{self.plate.layers}-layer plate"
        return (
            f"{name}: h={self.plate.thickness_nm:.1f} nm, chi={self.chi:.2f} "
            f"({regime(self.chi)}); at delta={self.tip.depth_nm:.2f} nm a Hertz "
            f"fit reads {self.factor:.2f}x the true modulus "
            f"(closed forms disagree by {100 * self.closed_form_spread:.0f}%)"
        )


def _nanoindent() -> tuple[Any, Any, Any]:
    try:
        from nanoindent import IndentationSolver, SimulationConfig, analytics
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(NANOINDENT_NOTE) from exc
    return SimulationConfig, IndentationSolver, analytics


def correction(
    plate: Plate,
    tip: Tip,
    *,
    substrate: Literal["bonded", "unbonded"] = "bonded",
    mesh_size_contact_nm: float = 0.05,
) -> Correction:
    """Solve the plate and report how far a Hertz fit would be off.

    `substrate` is consequential and is not a free choice to be made quietly:
    an origami plate electrostatically pinned to mica through Mg2+ is closer to
    bonded, but a plate that can slide is roughly half as stiff. If the
    experiment cannot establish which, run both and report the bracket.
    """
    SimulationConfig, IndentationSolver, analytics = _nanoindent()
    import numpy as np

    chi = thin_film_parameter(plate, tip)
    depth = np.array([tip.depth_nm])
    domain_nm = min(max(plate.footprint_nm / 2, 20.0), 100.0)

    cfg = SimulationConfig(
        tip_shape="paraboloid",
        R=tip.radius_nm,
        h=plate.thickness_nm,
        L=domain_nm,
        substrate=substrate,
        E=_PROBE_MODULUS_MPA,
        nu=_POISSON,
        delta_max=tip.depth_nm,
        n_steps=8,
        formulation="mixed",
        mesh_size_contact=mesh_size_contact_nm,
        mesh_size_edge=3.0,
    )
    curve = IndentationSolver(cfg).run()
    kw = dict(R=tip.radius_nm, E=_PROBE_MODULUS_MPA)
    return Correction(
        plate=plate,
        tip=tip,
        chi=chi,
        hertz_pn=float(analytics.hertz_force(depth, nu=_POISSON, **kw)[0]),
        fe_pn=float(np.asarray(curve.force)[-1]),
        dimitriadis_pn=float(
            analytics.dimitriadis_bonded_incompressible(depth, h=plate.thickness_nm, **kw)[0]
        ),
        bec_pn=float(analytics.garcia_bec_force(depth, nu=_POISSON, h=plate.thickness_nm, **kw)[0]),
    )


def thickness_ladder() -> tuple[Plate, ...]:
    """The constructs of the calibration experiment.

    One footprint, one lattice, one staple core; only the layer count changes.
    That is the whole design: DNA does not become stiffer because fewer layers
    were stacked, so any rise in apparent modulus as the plate thins is the
    substrate, not the material. The rise has a known functional form, which is
    what turns the artefact into a calibration.
    """
    return (
        Plate(layers=1, footprint_nm=100.0, name="single layer"),
        Plate(layers=2, footprint_nm=100.0, name="two layers"),
        Plate(layers=3, footprint_nm=100.0, name="three layers"),
        Plate(layers=6, footprint_nm=100.0, name="six layers"),
    )


#: Correction factors produced by `correction()` against nanoindent at
#: R = 10 nm, delta = 0.4 nm, bonded, incompressible. The depth is part of the
#: measurement, not a detail: see `Correction.factor`. Pinned here so this
#: project's documents and tests have a reference without requiring a private
#: package to be installed; `test_mechanics.py` checks them against a live
#: nanoindent whenever one is importable, so they cannot silently rot.
MEASURED_FACTORS: Final[dict[int, float]] = {
    1: 5.06,
    2: 2.15,
    3: 1.61,
}

"""Synthetic twin for the fast shape predictor: designs whose shape is known exactly.

AFM has a twin (`imaging.synthetic`): scans of known contents, pinned in
tests, and it found a plane-fit bug no real scan would have exposed. This is
the same thing for `mechanics.beam` (#15). Each twin is a design built here
together with the answer that a textbook -- not the model -- gives for it, so
an agent that changes the predictor can grade the change in a second, before
touching a real design or an oxDNA run.

**The family.** The current six-helix bundle, with deletions on some of its
helices. A helix carrying one deletion every `n` bp wants to be `1/n`
shorter; bonded to the others by crossovers it cannot be, and the section
bends. Composite-beam theory (any strength-of-materials text, e.g.
Timoshenko & Gere) gives the curvature exactly for a section of identical
helices, each of stretch modulus S and bending rigidity EI, at positions r_i
about the centroid:

    kappa = S * | sum_i eps_i r_i | / (S * sum_i r_i^2 / 2 + N * EI)

because a hexagon of circumradius D has the same second moment about every
axis through its centre, S * 3 D^2. The curvature points along
sum_i eps_i r_i: toward the short side. Two consequences that need no
formula at all, and are the family's controls:

- **no deletions** -- straight;
- **opposite helices shortened equally** -- sum_i eps_i r_i = 0 by symmetry,
  so the bundle shortens and stays straight -- up to the crossover pattern,
  which differs helix to helix (see STRAIGHT_REL_TOL). A predictor with a
  lever arm or a sign wrong bends it.

The formula has no twist-stretch coupling, so twins are graded with it off
(`BeamParameters(twist_stretch_pn_nm=0)`). With it on there is no closed
form, which is exactly why a measured reference is still wanted
(`dobladillo benchmark`, the Dietz 2009 case).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.mechanics import beam
from dobladillo.mechanics.beam import BeamParameters, ShapePrediction

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import scadnano as sc

#: The composite-beam formula has no twist-stretch coupling, so twins are
#: graded with the model's coupling switched off and everything else default.
TWIN_PARAMETERS: Final = BeamParameters(twist_stretch_pn_nm=0.0)

#: Where the first deletion sits, bp past the helix's first paired base. Mid-
#: domain: clear of every crossover of the current bundle (checked when built).
DELETION_PHASE_BP: Final = 3

#: Relative tolerance on radius, and absolute on direction, for grading. The
#: model reproduces the formula to 0.02%, so 1% is a regression, not noise.
RADIUS_REL_TOL: Final = 0.01
DIRECTION_TOL_DEG: Final = 1.0

#: A symmetric twin is straight only up to its crossover pattern, which is not
#: the same on every helix: shortening helices 0 and 3 together leaves a
#: residual curvature of 0.1% of what helix 0 alone produces. So "straight"
#: is graded as under 1% of that -- ten times the discreteness, and a hundred
#: times below a real one-sided bend.
STRAIGHT_REL_TOL: Final = 0.01


@dataclass(frozen=True)
class BeamTwin:
    """A design and its exact answer."""

    name: str
    design: sc.Design
    #: Helix -> deletion period in bp; empty for the unmodified bundle.
    shortened: dict[int, int]
    #: None when the answer is "straight".
    radius_nm: float | None
    direction_deg: float | None
    source: str
    #: For a symmetric twin: the curvature ONE of its shortened helices would
    #: give alone, the scale against which "straight" is judged. None when
    #: nothing is shortened, and "straight" means the model's own threshold.
    reference_curvature_per_nm: float | None = None
    parameters: BeamParameters = field(default_factory=lambda: TWIN_PARAMETERS)

    @property
    def straight(self) -> bool:
        return self.radius_nm is None


@dataclass(frozen=True)
class TwinGrade:
    twin: BeamTwin
    prediction: ShapePrediction
    ok: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "twin": self.twin.name,
            "ok": self.ok,
            "expected_radius_nm": (
                None if self.twin.radius_nm is None else round(self.twin.radius_nm, 1)
            ),
            "predicted_radius_nm": (
                None if self.prediction.straight else round(self.prediction.radius_nm, 1)
            ),
            "expected_direction_deg": self.twin.direction_deg,
            "predicted_direction_deg": (
                None if self.prediction.straight else round(self.prediction.bend_direction_deg, 1)
            ),
            "source": self.twin.source,
        }


def section_positions_nm(design: sc.Design, spacing_nm: float) -> dict[int, np.ndarray]:
    """Helix axes about the section's centroid, neighbours `spacing_nm` apart."""
    import scadnano as sc

    native = 2 * design.geometry.helix_radius + design.geometry.inter_helix_gap
    xy = {}
    for idx, helix in design.helices.items():
        pos = sc.grid_position_to_position(helix.grid_position, design.grid, design.geometry)
        xy[idx] = np.array([pos.x, pos.y]) * (spacing_nm / native)
    centre = np.mean(list(xy.values()), axis=0)
    return {idx: p - centre for idx, p in xy.items()}


def composite_beam(
    positions: dict[int, np.ndarray], strains: dict[int, float], p: BeamParameters
) -> tuple[float | None, float | None]:
    """(radius nm, direction deg) from composite-beam theory; (None, None) if straight.

    `strains` maps a helix to the fraction by which it wants to be shorter.
    The section's second moment is taken about each axis from the positions,
    and must be the same about both -- true of the hexagon, and checked, since
    the one-number formula is wrong for a section that is not isotropic.
    """
    S, EI = p.stretch_pn, p.bend_pn_nm2
    r = np.array(list(positions.values()))
    ixx, iyy, ixy = (r[:, 1] ** 2).sum(), (r[:, 0] ** 2).sum(), (r[:, 0] * r[:, 1]).sum()
    if not (math.isclose(ixx, iyy, rel_tol=1e-6) and abs(ixy) < 1e-6 * ixx):
        raise ValueError("section is not isotropic; the one-number formula does not apply")
    moment = S * sum((eps * positions[h] for h, eps in strains.items()), np.zeros(2))
    if np.linalg.norm(moment) < 1e-12:
        return None, None
    kappa = float(np.linalg.norm(moment) / (S * ixx + len(positions) * EI))
    return 1.0 / kappa, float(np.degrees(np.arctan2(moment[1], moment[0])) % 360.0)


def shortened_bundle(shortened: dict[int, int], *, name: str | None = None) -> BeamTwin:
    """The current 6HB with one deletion every `period` bp on each named helix."""
    from dobladillo.mechanics.beam import _crossover_ends
    from dobladillo.parts.bundle import DEFAULT_LENGTH, END_NT, six_helix_bundle

    design = six_helix_bundle().design
    crossover_offsets: dict[int, set[int]] = {}
    for a, b in _crossover_ends(design):
        for helix, offset in (a, b):
            crossover_offsets.setdefault(helix, set()).add(offset)
    for helix, period in shortened.items():
        offsets = range(END_NT + DELETION_PHASE_BP, END_NT + DEFAULT_LENGTH, period)
        clash = crossover_offsets.get(helix, set()) & set(offsets)
        if clash:
            raise ValueError(f"deletions on helix {helix} would land on crossovers at {clash}")
        for offset in offsets:
            design.add_deletion(helix, offset)

    p = TWIN_PARAMETERS
    positions = section_positions_nm(design, p.interhelix_nm)
    radius, direction = composite_beam(positions, {h: 1.0 / n for h, n in shortened.items()}, p)
    reference = None
    if radius is None and shortened:
        helix, period = next(iter(shortened.items()))
        alone, _ = composite_beam(positions, {helix: 1.0 / period}, p)
        reference = None if alone is None else 1.0 / alone
    label = ", ".join(f"helix {h} 1/{n}" for h, n in sorted(shortened.items())) or "none"
    return BeamTwin(
        name=name or f"6hb shortened: {label}",
        design=design,
        shortened=dict(shortened),
        radius_nm=radius,
        direction_deg=direction,
        source=(
            "composite-beam theory (e.g. Timoshenko & Gere): kappa = S |sum eps_i r_i| / "
            "(S sum r_i^2 / 2 + N EI)"
            if radius is not None
            else "symmetry: no net moment about the centroid, so no bend"
        ),
        reference_curvature_per_nm=reference,
    )


def standard_twins() -> tuple[BeamTwin, ...]:
    """The set a predictor change is graded against.

    One helix at 1/21 is the benchmark's composite-beam case (R = 168.0 nm).
    Halving the strain must double the radius; the opposite helix must bend
    the other way; opposite helices together and no deletions must stay
    straight.
    """
    return (
        shortened_bundle({0: 21}),
        shortened_bundle({0: 42}),
        shortened_bundle({3: 21}),
        shortened_bundle({0: 21, 3: 21}, name="6hb shortened: helices 0 and 3, opposite"),
        shortened_bundle({}, name="6hb unmodified"),
    )


def grade(
    twins: Sequence[BeamTwin] | None = None,
    *,
    predictor: Callable[[sc.Design, BeamParameters], ShapePrediction] | None = None,
) -> tuple[TwinGrade, ...]:
    """Run the predictor on every twin and say which answers it got right.

    `beam.predict` is looked up at call time, so a test can swap in a broken
    predictor and see the twins catch it.
    """
    run = predictor or beam.predict
    graded = []
    for twin in twins if twins is not None else standard_twins():
        shape = run(twin.design, twin.parameters)
        if twin.radius_nm is None or twin.direction_deg is None:
            scale = twin.reference_curvature_per_nm
            ok = shape.straight or (
                scale is not None and shape.curvature_per_nm <= STRAIGHT_REL_TOL * scale
            )
        else:
            turn = abs((shape.bend_direction_deg - twin.direction_deg + 180.0) % 360.0 - 180.0)
            ok = (
                not shape.straight
                and math.isclose(shape.radius_nm, twin.radius_nm, rel_tol=RADIUS_REL_TOL)
                and turn <= DIRECTION_TOL_DEG
            )
        graded.append(TwinGrade(twin=twin, prediction=shape, ok=ok))
    return tuple(graded)

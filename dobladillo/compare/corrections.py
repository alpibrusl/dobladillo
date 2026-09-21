"""Turning an AFM footprint into something a simulation can be compared with.

Only one correction here is large enough to matter, and it is large: a tip of
finite radius makes everything wider than it is.

The geometry, because the number is worth deriving rather than quoting. Take a
rigid spherical tip of radius R scanning a plateau of height h with a vertical
edge at x = 0, and let the apex trace the surface. While the sphere rides the
top corner at (0, h), its centre is at (x, z + R) and touches that corner, so

    x^2 + (z + R - h)^2 = R^2   ->   z(x) = h - R + sqrt(R^2 - x^2)

The image therefore extends past the true edge, reaching the substrate at
x = sqrt(2Rh - h^2). But `imaging.particles` measures at HALF height, and that
convention is exactly why: setting z = h/2 gives

    sqrt(R^2 - x^2) = R - h/2   ->   x = sqrt(R h - h^2 / 4)

which is smaller. For a 10 nm tip on a 2 nm plate, 4.36 nm per side rather than
6.00. Both edges are affected, so a width is over-measured by twice it.

Against a 36 nm rectangle that is 8.7 nm, or 24%. Against its 191 nm length it
is 4.6%. Tip radius is the dominant systematic in any width this project
reports, which is also why a partner should measure the tip before and after.

What is deliberately NOT corrected here is height. Origami on mica images
lower than it is -- tip force and adsorption both flatten it -- and there is no
geometric correction for that, only a calibration. Inventing one would turn an
honest disagreement into an invisible one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from dobladillo.compare.observation import Conditions, Observation

#: Nominal apex radius of a sharp imaging tip, nm. A starting value only: it
#: blunts with use, enters the correction as a square root, and is the reason
#: a tip should be characterised at the start and end of a session.
DEFAULT_TIP_RADIUS_NM = 10.0

#: Fractional uncertainty to assume on an uncharacterised tip radius. A nominal
#: 10 nm tip is routinely anywhere from 8 to 20 nm in use, and pretending
#: otherwise would make the corrected width look better determined than it is.
TIP_RADIUS_UNCERTAINTY = 0.4


def half_height_broadening_nm(*, tip_radius_nm: float, feature_height_nm: float) -> float:
    """Lateral over-measurement per side, at the half-height contour.

    Returns 0 for a feature taller than the tip radius allows this model to
    describe, rather than a complex number: past that the sphere no longer
    rides the top corner and the geometry above does not hold.
    """
    if tip_radius_nm <= 0:
        raise ValueError(f"tip radius must be positive, got {tip_radius_nm}")
    if feature_height_nm <= 0:
        raise ValueError(f"feature height must be positive, got {feature_height_nm}")
    inner = tip_radius_nm * feature_height_nm - feature_height_nm**2 / 4.0
    return math.sqrt(inner) if inner > 0 else 0.0


@dataclass(frozen=True)
class Deconvolved:
    """A corrected observation and what the correction cost in certainty."""

    observation: Observation
    broadening_nm: float
    tip_radius_nm: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "broadening_per_side_nm": round(self.broadening_nm, 2),
            "removed_nm": round(2 * self.broadening_nm, 2),
            "tip_radius_nm": self.tip_radius_nm,
            "observation": self.observation.as_dict(),
        }


def deconvolve_tip(
    observation: Observation,
    *,
    feature_height_nm: float,
    tip_radius_nm: float = DEFAULT_TIP_RADIUS_NM,
    radius_uncertainty: float = TIP_RADIUS_UNCERTAINTY,
) -> Deconvolved:
    """Remove tip broadening from an AFM lateral dimension.

    The uncertainty grows: an uncharacterised tip radius is the largest thing
    not known about the result, and propagating it is what stops a corrected
    width from looking more certain than the measurement it came from.
    """
    if observation.definition != "afm_half_height":
        raise ValueError(
            f"tip deconvolution applies to an afm_half_height observation, "
            f"not to {observation.definition!r}"
        )

    broadening = half_height_broadening_nm(
        tip_radius_nm=tip_radius_nm, feature_height_nm=feature_height_nm
    )
    # d(2*sqrt(Rh - h^2/4))/dR = h / sqrt(Rh - h^2/4), times the radius spread.
    if broadening > 0:
        from_radius = feature_height_nm / broadening * (radius_uncertainty * tip_radius_nm)
    else:  # pragma: no cover - degenerate geometry
        from_radius = 0.0
    existing = observation.uncertainty_nm or 0.0
    corrected = Observation(
        quantity=observation.quantity,
        value_nm=observation.value_nm - 2 * broadening,
        definition="simulated_extent",
        origin=observation.origin,
        conditions=observation.conditions,
        uncertainty_nm=math.hypot(existing, from_radius),
        n=observation.n,
        note=(
            f"tip-deconvolved: {2 * broadening:.1f} nm removed for a "
            f"{tip_radius_nm:.0f} nm tip on a {feature_height_nm:.1f} nm feature"
        ),
    )
    return Deconvolved(observation=corrected, broadening_nm=broadening, tip_radius_nm=tip_radius_nm)


def designed(quantity: str, value_nm: float, *, model: str = "scadnano geometry") -> Observation:
    """A designed dimension. No uncertainty, because it is not a measurement."""
    return Observation(
        quantity=quantity,
        value_nm=value_nm,
        definition="design_geometry",
        origin="designed",
        conditions=Conditions(model=model),
    )

"""The scanner's lateral error, from reference particles landed at random angles.

**The model.** For particle i, each matched mark sits at

    image = S . R(theta_i) . H_i . D . design + t_i

in the raster frame (nm; x along a scan line, y down the lines), where

- S = [[sx, k], [0, sy]] is the SCANNER: how many reported nm it gives per
  true nm along x and y, and its skew, k = sy tan(skew). Upper triangular,
  because any 2D linear map is that times a rotation, and a scanner's
  rotation relative to particles that land at random angles is unobservable
  (it is absorbed by the theta_i);
- R(theta_i) is the particle's in-plane rotation and H_i = diag(1, +-1) its
  handedness (which face is up), both from the match;
- D = diag(1, a) is the OBJECT's anisotropy: a is the ratio of its actual
  across-helix scale to the nominal one. The along-helix scale is fixed at
  the nominal rise: that is the reference, the one dimension of a DNA-origami
  tile that does not depend much on conditions. The inter-helix spacing
  does, which is why it is fitted rather than trusted
  (`parts.calibration_tile`);
- t_i is the particle's position (eliminated exactly by centring each
  particle's marks, since it enters linearly).

**Why sx, sy, k and a can be told apart at all.** On one particle they
cannot: S . R . D has four numbers and so do (sx, sy, k, a) with theta
besides, one too many. What separates them is that the scanner's anisotropy
is fixed in the IMAGE frame while the object's rotates with each particle.
Write it as metric tensors: S R D D R^T S^T. For the right a, taking D out
leaves S S^T, the same on every particle; for a wrong a' it leaves
S R diag(1, (a/a')^2) R^T S^T, which changes with theta. So a is identified
by how the particles' apparent shapes vary with their angle -- through
cos 2theta and sin 2theta, since an anisotropy looks the same turned by a
half turn -- and S by what stays fixed. Particles that all landed at nearly
the same angle carry no such variation, and the fit REFUSES them
(`MIN_ANGLE_SPREAD`), and refuses any fit whose covariance still ties a to
sx or sy (`MAX_CORRELATION`), rather than report numbers that only a prior
could have separated.

**Uncertainty, GUM-style.** Three components, combined in quadrature:

1. **statistical** -- a bootstrap over PARTICLES (they are the independent
   units: every mark on one particle shares its pose, its landing and its
   deformation). Covers centroid noise, pixelisation, missing marks, pose,
   and particle-to-particle variation in this image set.
2. **reference scale** -- the reference's relative standard uncertainty per
   axis, times a sensitivity coefficient measured by refitting with the
   reference stretched. Along x it passes one for one into sx and sy (a
   reference that is 1% long makes the scanner look 1% short). When a is
   fitted, the reference's y uncertainty is not a component: y is what a
   measures.
3. **reference features** -- a per-feature position uncertainty, if the
   reference declares one, by Monte Carlo over perturbed references.

Each quantity is reported as a value, its standard uncertainty u and the
expanded uncertainty U = 2u (k = 2). What is NOT included is listed in every
result (`NOT_INCLUDED`): above all, the reference's dimensions AS PREPARED.
A nominal reference -- a design, a datasheet's typical value -- gives
`traceable: false` whatever the error bars; only a certified one can make a
calibration traceable, and this module cannot check the certificate.

**Reporting convention.** `scale_x`/`scale_y` are the SCANNER's (reported nm
per true nm), which is what an error model is written in; `correction_x`/
`correction_y` are their reciprocals, the factors to multiply the
instrument's nm by, and `correction_matrix` is the full S^-1 including skew.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.calibration.features import Detection, ParticleMatch, detect

if TYPE_CHECKING:
    from dobladillo.calibration.reference import ReferenceGeometry
    from dobladillo.imaging.heightmap import HeightMap

__all__ = [
    "COVERAGE_FACTOR",
    "CalibrationRefused",
    "LateralCalibration",
    "Quantity",
    "calibrate_lateral",
    "fit_scanner",
]

#: k for the expanded uncertainty: about 95% coverage for a normal
#: distribution with many effective degrees of freedom (GUM 6.3).
COVERAGE_FACTOR: Final = 2.0

#: Fewer particles than this and the fit refuses. Chosen: a bootstrap over
#: fewer than about ten units underestimates its spread, and the angles of
#: fewer than ten particles rarely cover the circle.
MIN_PARTICLES: Final = 10

#: The particles' doubled angles must spread at least this far: one minus
#: the mean resultant length of exp(2i theta), 0 when every particle lies
#: at the same angle (or the same one turned by a half turn), about 1 when
#: they are uniform. 0.1 is reached by angles spread uniformly over about
#: 45 degrees; measured on synthetic tiles, the anisotropy's correlation
#: with the scanner's x scale is then about 0.9. Chosen, and deliberately
#: permissive: `MAX_CORRELATION` is the check that the spread actually
#: separated the parameters.
MIN_ANGLE_SPREAD: Final = 0.1

#: After the fit, the correlation between the object anisotropy and each
#: scanner parameter must be below this in magnitude. Chosen: above it,
#: the data cannot say whether a sheet looks wide because it is wide or
#: because the scanner stretched it, and the uncertainties would be carried
#: by the linearisation rather than by the data.
MAX_CORRELATION: Final = 0.95

#: Bootstrap resamples. Chosen: the standard uncertainty of a standard
#: deviation estimated from B resamples is about 1/sqrt(2B), 5% at 200.
BOOTSTRAP: Final = 200

#: Monte Carlo draws for a per-feature reference uncertainty. Chosen.
FEATURE_DRAWS: Final = 50

#: Relative stretch used to measure the sensitivity to the reference's
#: scale. Small enough to be linear, large enough to be well above the
#: solver's tolerance. Chosen.
STRETCH: Final = 1e-3

#: Images below which the statistical u is warned about. Measured on 200
#: synthetic sessions (2026-09-29, #30): with 4 images of 10 tiles the errors
#: scattered 0.98-1.07 times the reported u for every parameter; with 2 images
#: of 20, scale_x scattered 1.18 times it (about 3.6 standard errors from 1)
#: while the rest stayed near 1. Errors shared by the particles of one image
#: average out only across images, and a bootstrap over particles cannot see
#: them. So: spread the particles over at least this many images.
MIN_IMAGES_FOR_HONEST_U: Final = 4

INCLUDED: Final = (
    "statistical: bootstrap over particles (centroid noise, pixelisation, missing marks, "
    "pose, particle-to-particle variation within these images)",
    "reference scale: the reference's relative uncertainty along x (and along y when the "
    "object anisotropy is not fitted), through sensitivity coefficients measured by refitting",
    "reference features: the reference's per-feature position uncertainty, by Monte Carlo "
    "(only when it declares one)",
)

NOT_INCLUDED: Final = (
    "the reference's dimensions AS PREPARED: a nominal reference is its design or datasheet; "
    "a folded, deposited and dried object can differ by several percent with buffer, Mg2+, "
    "deposition and drying, and any along-x difference passes one for one into scale_x and "
    "scale_y",
    "scanner non-linearity and hysteresis: the model is linear over the field; a non-linear "
    "scanner raises the residual rms and makes the result depend on where the particles lie",
    "drift and anything else that changes during the scan (see calibration.drift)",
    "the z calibration: no height enters this fit",
    "deformation common to every particle, which is indistinguishable from the reference "
    "being wrong; particle-to-particle deformation is in the statistical term",
    "errors shared by all particles of one image (e.g. an image's own line offsets or "
    "tilt): a bootstrap over particles cannot see them. Over 200 synthetic sessions the "
    "errors scattered 0.98-1.07 times u with 4 images, but scale_x 1.18 times u with 2 "
    "(MIN_IMAGES_FOR_HONEST_U)",
    "the approximation behind k = 2: normal errors with many effective degrees of freedom; "
    "with few particles it underestimates",
)


class CalibrationRefused(ValueError):
    """The data cannot support the calibration asked of it; the message says why."""


@dataclass(frozen=True)
class Quantity:
    """A calibrated value and its uncertainty budget, all standard (k=1) but `expanded`."""

    value: float
    unit: str
    u_statistical: float
    u_reference_scale: float = 0.0
    u_reference_features: float = 0.0

    @property
    def u(self) -> float:
        return math.sqrt(
            self.u_statistical**2 + self.u_reference_scale**2 + self.u_reference_features**2
        )

    @property
    def expanded(self) -> float:
        return COVERAGE_FACTOR * self.u

    def covers(self, truth: float, *, statistical_only: bool = False) -> bool:
        u = self.u_statistical if statistical_only else self.u
        return abs(self.value - truth) <= COVERAGE_FACTOR * u

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "u": self.u,
            "U_k2": self.expanded,
            "budget": {
                "statistical": self.u_statistical,
                "reference_scale": self.u_reference_scale,
                "reference_features": self.u_reference_features,
            },
        }


@dataclass(frozen=True)
class LateralCalibration:
    """What the scanner gets wrong laterally, and how well that is known."""

    scale_x: Quantity
    scale_y: Quantity
    skew_deg: Quantity
    anisotropy: Quantity
    correction_x: Quantity
    correction_y: Quantity
    correction_matrix: np.ndarray
    residual_rms_nm: Quantity
    n_particles: int
    n_features: int
    angle_spread: float
    correlation: dict[str, float]
    anisotropy_fitted: bool
    reference: ReferenceGeometry
    bootstrap: int
    rejected: dict[str, int] = field(default_factory=dict)
    n_images: int = 0
    warnings: tuple[str, ...] = ()

    @property
    def traceable(self) -> bool:
        return self.reference.traceable

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": "image = S R(theta_i) H_i diag(1, a) design + t_i; "
            "S = [[scale_x, scale_y tan(skew)], [0, scale_y]], raster frame "
            "(x along a line, y down the lines)",
            "scanner": {
                "scale_x": self.scale_x.as_dict(),
                "scale_y": self.scale_y.as_dict(),
                "skew_deg": self.skew_deg.as_dict(),
                "meaning": "reported nm per true nm; positive skew leans the imaged y axis "
                "towards +x",
            },
            "correction": {
                "x": self.correction_x.as_dict(),
                "y": self.correction_y.as_dict(),
                "matrix": [[float(v) for v in row] for row in self.correction_matrix],
                "meaning": "multiply the instrument's nm by these (the matrix is S^-1, skew "
                "included)",
            },
            "object_anisotropy": {
                **self.anisotropy.as_dict(),
                "fitted": self.anisotropy_fitted,
                "meaning": "actual / nominal scale of the reference along its y (across the "
                "helices for the calibration tile)",
            },
            "n_particles": self.n_particles,
            "n_features": self.n_features,
            "n_images": self.n_images,
            "warnings": list(self.warnings),
            "residual_rms_nm": self.residual_rms_nm.as_dict(),
            "angle_spread": round(self.angle_spread, 4),
            "correlation": {k: round(v, 4) for k, v in self.correlation.items()},
            "coverage_factor": COVERAGE_FACTOR,
            "bootstrap_resamples": self.bootstrap,
            "rejected_particles": dict(sorted(self.rejected.items())),
            "traceable": self.traceable,
            "reference": {
                "name": self.reference.name,
                "status": self.reference.status,
                "source": self.reference.source,
                "provenance": self.reference.provenance,
                "relative_uncertainty": list(self.reference.relative_uncertainty),
            },
            "uncertainty_includes": list(INCLUDED),
            "uncertainty_excludes": list(NOT_INCLUDED),
        }


# ------------------------------------------------------------------ the solver


@dataclass(frozen=True)
class _Data:
    """Matched marks, each particle's centred on its own mean (which removes t_i)."""

    design: np.ndarray  # (M, 2)
    observed: np.ndarray  # (M, 2)
    particle: np.ndarray  # (M,) index into the particles
    handedness: np.ndarray  # (N,)
    theta0: np.ndarray  # (N,)

    @property
    def n(self) -> int:
        return len(self.handedness)


def _data(
    matches: Sequence[ParticleMatch], positions: dict[str, np.ndarray] | None = None
) -> _Data:
    design, observed, index = [], [], []
    for i, m in enumerate(matches):
        q = m.design_nm if positions is None else np.array([positions[n] for n in m.names])
        design.append(q - q.mean(axis=0))
        observed.append(m.observed_nm - m.observed_nm.mean(axis=0))
        index.append(np.full(len(q), i))
    return _Data(
        design=np.concatenate(design),
        observed=np.concatenate(observed),
        particle=np.concatenate(index),
        handedness=np.array([m.handedness for m in matches], dtype=float),
        theta0=np.radians([m.angle_deg for m in matches]),
    )


def _model(
    p: np.ndarray, data: _Data, fit_a: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sx, sy, k = p[0], p[1], p[2]
    a = p[3] if fit_a else 1.0
    theta = p[4 if fit_a else 3 :]
    c = np.cos(theta)[data.particle]
    s = np.sin(theta)[data.particle]
    x = data.design[:, 0]
    w = data.handedness[data.particle] * data.design[:, 1]
    y = a * w
    rx = c * x - s * y
    ry = s * x + c * y
    return sx * rx + k * ry, sy * ry, rx, ry, c * w, s * w


def _residuals(p: np.ndarray, data: _Data, fit_a: bool) -> np.ndarray:
    px, py, *_ = _model(p, data, fit_a)
    return np.concatenate([px - data.observed[:, 0], py - data.observed[:, 1]])


def _jacobian(p: np.ndarray, data: _Data, fit_a: bool) -> np.ndarray:
    sx, sy, k = p[0], p[1], p[2]
    _, _, rx, ry, cw, sw = _model(p, data, fit_a)
    m = len(data.particle)
    g = 4 if fit_a else 3
    jac = np.zeros((2 * m, g + data.n))
    jac[:m, 0] = rx
    jac[m:, 1] = ry
    jac[:m, 2] = ry
    if fit_a:
        jac[:m, 3] = -sx * sw + k * cw
        jac[m:, 3] = sy * cw
    rows = np.arange(m)
    jac[rows, g + data.particle] = -sx * ry + k * rx
    jac[m + rows, g + data.particle] = sy * rx
    return jac


def _solve(data: _Data, fit_a: bool, start: np.ndarray | None = None) -> np.ndarray:
    from scipy.optimize import least_squares

    if start is None:
        start = np.concatenate([[1.0, 1.0, 0.0], [1.0] if fit_a else [], data.theta0])
    result = least_squares(
        _residuals, start, jac=_jacobian, args=(data, fit_a), method="lm", xtol=1e-12
    )
    if not result.success:
        raise CalibrationRefused(f"the scanner fit did not converge: {result.message}")
    solution: np.ndarray = result.x
    return solution


def _summary(p: np.ndarray, data: _Data, fit_a: bool) -> np.ndarray:
    """(scale_x, scale_y, skew_deg, anisotropy, residual rms) from a solution."""
    r = _residuals(p, data, fit_a)
    m = len(data.particle)
    rms = math.sqrt(float((r[:m] ** 2 + r[m:] ** 2).mean()))
    return np.array([p[0], p[1], math.degrees(math.atan2(p[2], p[1])), p[3] if fit_a else 1.0, rms])


def _angle_spread(theta: np.ndarray) -> float:
    return 1.0 - float(abs(np.exp(2j * theta).mean()))


def _correlations(p: np.ndarray, data: _Data, fit_a: bool) -> dict[str, float]:
    """Parameter correlations from the linearised covariance at the solution."""
    jac = _jacobian(p, data, fit_a)
    cov = np.linalg.pinv(jac.T @ jac)
    sd = np.sqrt(np.clip(np.diag(cov), 1e-300, None))
    corr = cov / np.outer(sd, sd)
    out = {"scale_x~skew": float(corr[0, 2]), "scale_y~skew": float(corr[1, 2])}
    if fit_a:
        out |= {
            "anisotropy~scale_x": float(corr[3, 0]),
            "anisotropy~scale_y": float(corr[3, 1]),
            "anisotropy~skew": float(corr[3, 2]),
        }
    return out


def fit_scanner(
    matches: Sequence[ParticleMatch],
    reference: ReferenceGeometry,
    *,
    fit_anisotropy: bool | None = None,
    bootstrap: int = BOOTSTRAP,
    seed: int = 0,
    rejected: dict[str, int] | None = None,
) -> LateralCalibration:
    """Fit the scanner to matched particles, with a GUM-style uncertainty.

    `fit_anisotropy` defaults to the reference's own `free_axis == "y"`.
    Raises `CalibrationRefused` for no matches, too few particles, angles
    that cannot separate the scanner from the object, or a fit whose
    covariance says the same.
    """
    fit_a = reference.free_axis == "y" if fit_anisotropy is None else fit_anisotropy
    if not matches:
        raise CalibrationRefused(
            "no particle matched the reference"
            + (f" (rejected: {dict(sorted(rejected.items()))})" if rejected else "")
            + ". Nothing in these images carries its marks: wrong sample, marks face down "
            "or not resolved, or a pixel too coarse to separate them."
        )
    if len(matches) < MIN_PARTICLES:
        raise CalibrationRefused(
            f"{len(matches)} matched particles; the fit needs at least {MIN_PARTICLES} "
            "for the bootstrap to mean anything. Image more."
        )
    data = _data(matches)
    spread = _angle_spread(data.theta0)
    if fit_a and spread < MIN_ANGLE_SPREAD:
        raise CalibrationRefused(
            f"the particles' angles are too alike to separate the scanner from the object "
            f"(spread {spread:.3f} < {MIN_ANGLE_SPREAD}): the scanner's anisotropy is fixed "
            "in the image and the object's turns with each particle, so it takes particles "
            "at different angles to tell them apart. Image a region where they landed at "
            "random, or fix the anisotropy (fit_anisotropy=False) and accept the reference's "
            "y uncertainty."
        )
    solution = _solve(data, fit_a)
    correlation = _correlations(solution, data, fit_a)
    if fit_a:
        tied = {k: v for k, v in correlation.items() if k.startswith("anisotropy~")}
        worst = max(tied, key=lambda k: abs(tied[k]))
        if abs(tied[worst]) > MAX_CORRELATION:
            raise CalibrationRefused(
                f"the fit correlates {worst} at {tied[worst]:.3f} (limit {MAX_CORRELATION}): "
                "these particles' angles do not separate the scanner from the object"
            )
    central = _summary(solution, data, fit_a)

    # 1. statistical: bootstrap over particles.
    rng = np.random.default_rng(seed)
    g = 4 if fit_a else 3
    draws = []
    for _ in range(bootstrap):
        pick = rng.integers(0, len(matches), len(matches))
        resampled = _data([matches[i] for i in pick])
        start = np.concatenate([solution[:g], solution[g:][pick]])
        draws.append(_summary(_solve(resampled, fit_a, start), resampled, fit_a))
    u_stat = np.std(np.array(draws), axis=0, ddof=1)

    # 2. reference scale: sensitivity to a stretched reference, times its uncertainty.
    ux, uy = reference.relative_uncertainty
    u_scale = np.zeros(5)
    for axis, u_rel in ((0, ux), (1, uy)):
        if u_rel == 0 or (axis == 1 and fit_a):
            continue
        stretch = np.array([1.0, 1.0])
        stretch[axis] += STRETCH
        positions = {
            name: np.array(pos) * stretch
            for name, pos in zip(reference.names, reference.positions_nm, strict=True)
        }
        moved = _data(matches, positions)
        sensitivity = (_summary(_solve(moved, fit_a, solution), moved, fit_a) - central) / STRETCH
        u_scale = np.hypot(u_scale, sensitivity * u_rel)

    # 3. reference features: Monte Carlo over the declared per-feature uncertainty.
    u_feat = np.zeros(5)
    if reference.feature_uncertainty_nm > 0:
        mc = []
        for _ in range(FEATURE_DRAWS):
            positions = {
                name: pos + rng.normal(0.0, reference.feature_uncertainty_nm, 2)
                for name, pos in zip(reference.names, reference.positions_nm, strict=True)
            }
            moved = _data(matches, positions)
            mc.append(_summary(_solve(moved, fit_a, solution), moved, fit_a))
        u_feat = np.std(np.array(mc), axis=0, ddof=1)

    def quantity(i: int, unit: str) -> Quantity:
        return Quantity(
            value=float(central[i]),
            unit=unit,
            u_statistical=float(u_stat[i]),
            u_reference_scale=float(u_scale[i]),
            u_reference_features=float(u_feat[i]),
        )

    def reciprocal(q: Quantity) -> Quantity:
        f = 1.0 / q.value**2
        return Quantity(
            value=1.0 / q.value,
            unit="true nm per reported nm",
            u_statistical=q.u_statistical * f,
            u_reference_scale=q.u_reference_scale * f,
            u_reference_features=q.u_reference_features * f,
        )

    scale_x = quantity(0, "reported nm per true nm")
    scale_y = quantity(1, "reported nm per true nm")
    s = np.array([[solution[0], solution[2]], [0.0, solution[1]]])
    n_images = len({m.image for m in matches})
    warnings: tuple[str, ...] = ()
    if n_images < MIN_IMAGES_FOR_HONEST_U:
        warnings = (
            f"particles from {n_images} image(s): errors shared within an image are not in "
            f"the statistical u, which read up to ~18% low for scale_x with 2 images in "
            f"synthetic tests. Spread the particles over at least {MIN_IMAGES_FOR_HONEST_U} "
            "images.",
        )
    return LateralCalibration(
        scale_x=scale_x,
        scale_y=scale_y,
        skew_deg=quantity(2, "deg"),
        anisotropy=quantity(3, "actual / nominal")
        if fit_a
        else Quantity(value=1.0, unit="actual / nominal (fixed)", u_statistical=0.0),
        correction_x=reciprocal(scale_x),
        correction_y=reciprocal(scale_y),
        correction_matrix=np.linalg.inv(s),
        residual_rms_nm=Quantity(
            value=float(central[4]), unit="nm", u_statistical=float(u_stat[4])
        ),
        n_particles=len(matches),
        n_features=len(data.particle),
        angle_spread=spread,
        correlation=correlation,
        anisotropy_fitted=fit_a,
        reference=reference,
        bootstrap=bootstrap,
        rejected=dict(rejected or {}),
        n_images=n_images,
        warnings=warnings,
    )


def calibrate_lateral(
    images: Sequence[HeightMap],
    reference: ReferenceGeometry,
    *,
    fit_anisotropy: bool | None = None,
    bootstrap: int = BOOTSTRAP,
    seed: int = 0,
) -> tuple[LateralCalibration, tuple[Detection, ...]]:
    """Detect and match in every image, then fit them together.

    Images taken at the same scan size and settings only: the scanner's
    error depends on both, and pooling different ones fits an average of
    instruments that do not exist.
    """
    detections = tuple(detect(image, reference, image_index=i) for i, image in enumerate(images))
    matches = [m for d in detections for m in d.matches]
    rejected: dict[str, int] = {}
    for d in detections:
        for reason, count in d.rejected.items():
            rejected[reason] = rejected.get(reason, 0) + count
    result = fit_scanner(
        matches,
        reference,
        fit_anisotropy=fit_anisotropy,
        bootstrap=bootstrap,
        seed=seed,
        rejected=rejected,
    )
    return result, detections

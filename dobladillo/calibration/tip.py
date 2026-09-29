"""The tip, measured: grey-scale morphology after Villarrubia.

An AFM image is not the surface. The tip is a solid of finite size, and at
each position the feedback stops it at the height where some point of it --
not necessarily the apex -- first touches the sample. For a rigid tip on a
rigid sample that is the whole model, and it has an exact mathematical name:
the image is the surface **dilated** by the tip. Everything else follows from
taking that literally, including the two things this module exists for:
knowing how wide the tip is, and knowing how much of an image it invented.

`compare.corrections` models the tip as a sphere of a given radius. That
radius has to come from somewhere, and a number printed on the box is a
`Nominal`, which the toolchain refuses. This module is where a `Measured` one
comes from.

**Source.** Implemented from the published equations of J. S. Villarrubia,
"Algorithms for scanned probe microscope image simulation, surface
reconstruction, and tip estimation", J. Res. Natl. Inst. Stand. Technol. 102,
425 (1997), a work of the US government. No code was taken from any existing
implementation -- not Gwyddion's (GPL), not matsunagalab's differentiable
reconstruction, not any other. The derivations are written out below so they
can be checked against the paper rather than against somebody's program.

**Convention.** A tip is a small array `t` in nanometres, odd in both
dimensions, on the image's own pixel grid, drawn *apex up*: exactly what the
image of an infinitely sharp spike would look like. So t = 0 at the centre
(the apex), t <= 0 everywhere else, and the physical tip surface at lateral
offset v from the apex sits -t(v) above the apex. Offsets are (row, col).
With the apex at x and height h, the tip surface at x + v is at h - t(v), it
must clear the sample there, and the feedback stops at the lowest h that
clears it everywhere:

    image simulation         I(x) = max_v [ s(x + v) + t(v) ]      (dilation)

The surface at y lay under the tip at every apex position x, so
s(y) <= I(x) - t(y - x) for all x, and the least of those bounds is

    surface reconstruction   r(y) = min_v [ I(y - v) - t(v) ]      (erosion)

r is never below s -- it is an upper bound on the surface everywhere -- and
equals s wherever the tip actually touched. Between two tall features the
tip never reaches the floor, and r says only "no higher than this".

**Blind estimation.** At apex position x the tip touches the surface at some
offset w, unknown: s(x + w) = I(x) - t(w). The same surface point lay under
the tip at every other apex position x', so I(x) - t(w) <= I(x') - t(x+w-x').
Writing d = x + w - x':

    t(d) <= I(x + w - d) - I(x) + t(w)                                  (1)

and w can only be a contact if the surface point it would touch is no higher
than the image directly above it (apex over it, t(0) = 0, so s <= I):

    I(x) - I(x + w) <= t(w)                                             (2)

Neither t nor w is known. But an outer bound t_i >= t is: putting t_i in (2)
keeps every true contact in the candidate set, and putting it in (1) keeps
the bound valid, so

    t_{i+1}(d) = min( t_i(d),  min_x  max_{w : (2) holds for t_i}
                                     [ I(x + w - d) - I(x) + t_i(w) ] )

is again an outer bound, and no blunter than t_i. Start from t_0 = 0 -- a
flat punch the size of the array, blunter than any real tip -- and repeat
until it stops changing. At an isolated spike only w = 0 passes (2), and (1)
returns the image around the spike: the tip, in one step. That is the
structure of the paper's argument, re-derived here in this convention.

*Checked against the paper (2026-09-29, #29).* The paper draws the tip
reflected, p, with t(v) = p(-v). Substituting that and w = -d, (1) is its
Eq. (17) and (2) is its Eq. (19), i(x') - i(x' - d) <= p(d) with the apex at
the origin -- the same restriction, not an approximation of it. Its noise
rule (Sec. 6.3: change a tip value only when the new bound is lower by more
than `thresh`, and then to new + thresh) is `min(t_i, bound + tolerance)`
below. Applying the tolerance to (2) as well is this module's addition; it
admits more contacts, so it can only loosen the bound, never break it.

**Noise.** Noise makes an image locally sharper than the tip that made it,
and (1) would then return a tip sharper than the real one -- no longer an
outer bound. `threshold_nm` is the tolerance that prevents it: every image
difference is allowed to be off by that much, so (2) admits contacts within
it and (1) is loosened by it. The outer-bound guarantee holds while the
threshold exceeds the largest noise difference between pixels the estimate
uses, which for white noise of standard deviation sigma is a few sigma --
`THRESHOLD_SIGMA` says how many, and why. Too small a threshold does not
fail gently: the noise compounds from pass to pass into a tip far sharper
than the real one. The price of a safe one is an estimate blunter than the
tip: a flat cap about `threshold_nm` deep, which `apex_radius` is told to
step over, and a sideways widening, because the threshold admits contacts
near the apex that are not there. On the test fixtures the recovered
radius comes out 11-33% high for a sphere-on-cone tip and 34-53% high
for a paraboloid; it is an upper bound in practice, not an estimate.

**What was done to make it fast, and why the paper allows it.** The bound
holds for every image point on its own, so the minimum over any subset of
points is looser but still a valid outer bound. Four cuts:

- Only local maxima of the image (in their 3 x 3 neighbourhood) are used, by
  default. The reason they carry nearly all the information: a point on the
  flank of a sharp feature can be in contact with the feature's apex, so its
  admitted contacts include that one, and (1) through it returns the image
  around the apex -- no tighter than the apex point's own bound. Measured on
  the synthetic spike fixtures in the tests: the same apex radius to 0.3%,
  noise-free recovery still exact, and 25-40 times faster than every point.
- A point can only lower the tip at d if its own w = 0 term does, i.e. if the
  image drops below the current tip set down on it:
  min_d [ I(x - d) - t_i(d) ] < I(x) - threshold. That is one erosion for the
  whole image per pass, and it discards noise maxima on flat background.
- Of the points left, those with the fewest candidate contacts go first, up to
  a budget of candidate contacts per pass. Points used least often so far go
  before those used more, so repeated passes cycle through all of them.
- Points closer than twice the tip half-width to the edge are skipped:
  (1) needs the image at x + w - d.

Each pass then runs vectorised over points and over d, looping only over w.

**What it cannot do.** An outer bound is only as tight as the image is sharp.
Where the image has no feature narrower than the tip, (2) admits so many
contacts that (1) bounds nothing: a featureless image leaves the estimate
flat, and so does a surface made only of flat-topped blocks, because a flat
punch explains any image of monotone steps. A block staircase therefore
constrains the tip only when its geometry is supplied, which is
`known_surface_tip`. And a feature blunter than the tip returns the shape of
the *feature*, as a confident-looking but meaningless blunt tip; nothing
inside one image can tell the two apart. Both are reported rather than
hidden: an estimate that never closed within its array is flagged as
uninformative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from dobladillo.constants import HELIX_DIAMETER_NM
from dobladillo.imaging.heightmap import HeightMap
from dobladillo.readings import Measured, When

#: Floating-point slack in the contact test and the convergence test, nm. Not
#: a physical tolerance: without it, rounding can drop the true contact from
#: condition (2) of a noise-free image and make the estimate too sharp.
_EPS: Final = 1e-9

#: Passes of the blind refinement before giving up on convergence. Chosen,
#: not derived: on the synthetic spike and noise fixtures the estimate stops
#: changing within a handful of passes.
MAX_ITERATIONS: Final = 50

#: Candidate contacts (summed over points) processed per pass. Each costs one
#: tip-sized array operation, so this caps the work of a pass at about
#: 2e5 * size_px**2 element operations -- about a second for a 31 px tip.
#: Chosen for speed; a smaller budget converges in more passes, not to a
#: different answer.
CONTACT_BUDGET: Final = 200_000

#: Points handled together in one vectorised block. Memory, not accuracy:
#: each point carries a few tip-sized arrays.
_CHUNK: Final = 512

#: The noise threshold to use, in multiples of the image's pixel noise
#: (`resolution.pixel_noise`). Chosen from measurement, not derived: on the
#: spike fixtures in the tests (tips of 5-20 nm, noise 0.05-0.1 nm) a
#: threshold of 3 sigma let the noise compound into tips up to 20 nm SHARPER
#: than the truth, 4 sigma broke the outer bound by 0.1 nm, and 5 sigma never
#: broke it.
THRESHOLD_SIGMA: Final = 5.0

#: How far below the apex the radius is read, nm, by default. The convention:
#: the part of the tip that images a sample is the part within the sample's
#: height of the apex, and the samples here are single-layer origami and
#: duplexes, about one helix diameter tall. A radius is only meaningful with
#: its depth stated, because a real tip is a sphere on a cone and gets
#: "blunter" the deeper it is read.
APEX_DEPTH_NM: Final = HELIX_DIAMETER_NM

#: Fewer pixels than this in the fit band and no radius is reported. Four
#: parameters per fit; chosen so there are at least two points per parameter.
MIN_FIT_POINTS: Final = 8

#: The curvature must differ from zero by this many standard errors, or the
#: tip is reported as undetermined rather than as a very large radius.
CURVATURE_SIGMA: Final = 3.0

#: An estimate counts as informative when even its shallowest rim pixel lies
#: deeper than this many noise thresholds below the apex: it closed inside its
#: array. Chosen: one threshold is the cap noise leaves on any estimate, so
#: twice it is the least that shows the image constrained the tip at all.
RIM_THRESHOLDS: Final = 2.0


# ------------------------------------------------------------------ helpers


def tip_half_sizes(tip: np.ndarray) -> tuple[int, int]:
    """Validate a tip array and return its half-sizes (rows, cols)."""
    if tip.ndim != 2:
        raise ValueError(f"a tip is a 2D array, got {tip.ndim} dimensions")
    rows, cols = tip.shape
    if rows % 2 == 0 or cols % 2 == 0:
        raise ValueError(f"a tip array must be odd in both dimensions, got {tip.shape}")
    a, b = rows // 2, cols // 2
    if not math.isfinite(float(tip[a, b])) or abs(float(tip[a, b])) > 1e-6:
        raise ValueError(f"the tip's apex (its centre) must be 0, got {tip[a, b]}")
    finite = tip[np.isfinite(tip)]
    if finite.size and float(finite.max()) > 1e-6:
        raise ValueError("a tip is drawn apex up: every value must be <= 0")
    return a, b


def _check_size(size_px: int) -> int:
    if size_px < 3 or size_px % 2 == 0:
        raise ValueError(f"size_px must be odd and at least 3, got {size_px}")
    return size_px // 2


def dilate(surface: np.ndarray, tip: np.ndarray) -> np.ndarray:
    """The image a tip records of a surface: I(x) = max_v [s(x + v) + t(v)].

    Both arrays share one pixel size. Outside the surface array there is no
    surface, so near the border the image is made from what is inside it.
    A tip value of -inf means "no tip there", which lets a non-square tip sit
    in a square array.
    """
    a, b = tip_half_sizes(tip)
    rows, cols = surface.shape
    padded = np.full((rows + 2 * a, cols + 2 * b), -np.inf)
    padded[a : a + rows, b : b + cols] = surface
    out = np.full(surface.shape, -np.inf)
    for i in range(2 * a + 1):
        for j in range(2 * b + 1):
            value = float(tip[i, j])
            if math.isfinite(value):
                np.maximum(out, padded[i : i + rows, j : j + cols] + value, out=out)
    return out


def erode(image: np.ndarray, tip: np.ndarray) -> np.ndarray:
    """The highest surface consistent with an image: r(y) = min_v [I(y - v) - t(v)].

    Never below the true surface; equal to it wherever the tip touched.
    Outside the image array there is no constraint, so near the border the
    bound comes only from what was imaged.
    """
    a, b = tip_half_sizes(tip)
    rows, cols = image.shape
    padded = np.full((rows + 2 * a, cols + 2 * b), np.inf)
    padded[a : a + rows, b : b + cols] = image
    out = np.full(image.shape, np.inf)
    for i in range(2 * a + 1):
        for j in range(2 * b + 1):
            value = float(tip[i, j])
            if math.isfinite(value):
                ii, jj = 2 * a - i, 2 * b - j
                np.minimum(out, padded[ii : ii + rows, jj : jj + cols] - value, out=out)
    return out


def _radius_grid(pixel_nm: float, size_px: int) -> np.ndarray:
    a = _check_size(size_px)
    offsets = (np.arange(size_px) - a) * pixel_nm
    radius: np.ndarray = np.hypot(offsets[:, None], offsets[None, :])
    return radius


def paraboloid_tip(radius_nm: float, pixel_nm: float, size_px: int) -> np.ndarray:
    """A paraboloid of apex radius R: t = -r^2 / 2R. A test tip, and the
    shape the two-point resolution formula assumes."""
    if radius_nm <= 0 or pixel_nm <= 0:
        raise ValueError("radius and pixel size must be positive")
    r = _radius_grid(pixel_nm, size_px)
    tip: np.ndarray = -(r**2) / (2 * radius_nm)
    return tip


def sphere_cone_tip(
    radius_nm: float, pixel_nm: float, size_px: int, *, half_angle_deg: float = 20.0
) -> np.ndarray:
    """A sphere of radius R on a cone of the given half-angle, joined smoothly.

    The usual model of a sharpened silicon tip. The sphere meets the cone
    where its slope equals the cone's, at r = R cos(alpha); beyond, the flank
    falls at cot(alpha) per unit of radius. 20 degrees is a representative
    half-angle for a sharpened tip, and only a default for tests.
    """
    if radius_nm <= 0 or pixel_nm <= 0:
        raise ValueError("radius and pixel size must be positive")
    if not 0 < half_angle_deg < 90:
        raise ValueError(f"half-angle must be in (0, 90) degrees, got {half_angle_deg}")
    alpha = math.radians(half_angle_deg)
    r = _radius_grid(pixel_nm, size_px)
    r_t = radius_nm * math.cos(alpha)
    z_t = radius_nm - math.sqrt(radius_nm**2 - r_t**2)
    sphere = radius_nm - np.sqrt(np.maximum(radius_nm**2 - r**2, 0.0))
    cone = z_t + (r - r_t) / math.tan(alpha)
    tip: np.ndarray = -np.where(r <= r_t, sphere, cone)
    return tip


# ------------------------------------------------------------ apex radius


def _json_float(value: float, digits: int = 3) -> float | None:
    return round(value, digits) if math.isfinite(value) else None


@dataclass(frozen=True)
class ApexRadius:
    """A tip's apex radius, read at a stated depth, with what it is worth.

    `radius_nm` is the mean of a sphere fit and a paraboloid fit to the tip
    surface between `cap_nm` and `cap_nm + depth_nm` below the apex. A real
    apex is neither shape exactly, and the two bracket the conventions in
    use, so half their difference is one component of the uncertainty. The
    others are the paraboloid fit's own standard error and the spread of the
    radius over half and one and a half times the depth. All three are
    standard uncertainties, combined in quadrature.

    When the tip does not determine a radius -- the band runs off the array,
    has too few pixels, or is not significantly curved -- `determined` is
    False, the radius is NaN, and `reason` says why. A flat estimate from a
    featureless image lands here, not at a very large radius.
    """

    radius_nm: float
    uncertainty_nm: float
    depth_nm: float
    cap_nm: float
    sphere_nm: float
    paraboloid_nm: float
    components_nm: dict[str, float]
    n_points: int
    determined: bool
    reason: str = ""

    def as_measured(self, source: str, *, instrument: str | None = None) -> Measured[float]:
        """This radius as a `Measured` tip radius, for `compare.deconvolve_tip`."""
        if not self.determined:
            raise ValueError(f"no radius was determined: {self.reason}")
        return Measured(
            value=self.radius_nm,
            quantity="tip_radius",
            source=source,
            at=When.now(),
            instrument=instrument,
            uncertainty=self.uncertainty_nm,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "radius_nm": _json_float(self.radius_nm, 2),
            "uncertainty_nm": _json_float(self.uncertainty_nm, 2),
            "depth_nm": self.depth_nm,
            "cap_nm": self.cap_nm,
            "convention": (
                "mean of sphere and paraboloid fits to the tip surface between "
                "cap_nm and cap_nm + depth_nm below the apex"
            ),
            "sphere_nm": _json_float(self.sphere_nm, 2),
            "paraboloid_nm": _json_float(self.paraboloid_nm, 2),
            "components_nm": {k: _json_float(v, 3) for k, v in self.components_nm.items()},
            "n_points": self.n_points,
            "determined": self.determined,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _Fit:
    sphere_nm: float
    paraboloid_nm: float
    paraboloid_se_nm: float
    n_points: int
    problem: str


def _fit_band(tip: np.ndarray, pixel_nm: float, low_nm: float, high_nm: float) -> _Fit:
    """Sphere and paraboloid fits to the pixels between two depths below the apex."""
    a, b = tip.shape[0] // 2, tip.shape[1] // 2
    depth = -tip
    band = np.isfinite(depth) & (depth >= low_nm - _EPS) & (depth <= high_nm + _EPS)
    nan = float("nan")
    n = int(band.sum())
    if n < MIN_FIT_POINTS:
        return _Fit(nan, nan, nan, n, f"only {n} pixels in the fit band")
    edge = np.zeros_like(band)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    if bool((band & edge).any()):
        return _Fit(
            nan,
            nan,
            nan,
            n,
            "the fit band reaches the edge of the tip array: the tip is "
            "not resolved to this depth inside it (a larger array or a smaller depth)",
        )
    rows, cols = np.nonzero(band)
    y = (rows - a) * pixel_nm
    x = (cols - b) * pixel_nm
    z = depth[band]

    # Paraboloid, isotropic, apex free: z = c0 + c1 x + c2 y + c3 (x^2 + y^2).
    design = np.column_stack([np.ones(n), x, y, x**2 + y**2])
    coef, *_ = np.linalg.lstsq(design, z, rcond=None)
    residual = z - design @ coef
    dof = max(n - 4, 1)
    sigma2 = float(residual @ residual) / dof
    try:
        cov = sigma2 * np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return _Fit(nan, nan, nan, n, "the fit band is degenerate")
    c3, se3 = float(coef[3]), math.sqrt(max(float(cov[3, 3]), 0.0))
    if c3 <= 0 or c3 <= CURVATURE_SIGMA * se3:
        return _Fit(
            nan, nan, nan, n, f"the tip is not significantly curved (c = {c3:.3g} +- {se3:.2g})"
        )
    paraboloid = 1.0 / (2.0 * c3)
    paraboloid_se = se3 / (2.0 * c3**2)

    # Sphere, algebraic and centre free: x^2 + y^2 + z^2 = 2 x x0 + 2 y y0 + 2 z z0 + k.
    design_s = np.column_stack([2 * x, 2 * y, 2 * z, np.ones(n)])
    target = x**2 + y**2 + z**2
    s_coef, *_ = np.linalg.lstsq(design_s, target, rcond=None)
    x0, y0, z0, k = (float(v) for v in s_coef)
    r2 = k + x0**2 + y0**2 + z0**2
    sphere = math.sqrt(r2) if r2 > 0 else nan
    if not math.isfinite(sphere):
        return _Fit(nan, paraboloid, paraboloid_se, n, "the sphere fit has no real radius")
    return _Fit(sphere, paraboloid, paraboloid_se, n, "")


def apex_radius(
    tip: np.ndarray,
    pixel_nm: float,
    *,
    depth_nm: float = APEX_DEPTH_NM,
    cap_nm: float = 0.0,
) -> ApexRadius:
    """The radius of the tip's apex, fitted over a band of stated depth.

    Depth convention: the band is the tip surface between `cap_nm` and
    `cap_nm + depth_nm` below the apex. `cap_nm` is for estimates whose top
    is known to be flattened -- a blind estimate is the tip raised by up to
    its noise threshold and clipped at zero -- and the fits have a free
    height offset, so skipping the cap leaves the curvature below it intact.
    See `ApexRadius` for how the value and its uncertainty are formed.
    """
    tip_half_sizes(tip)
    if pixel_nm <= 0:
        raise ValueError(f"pixel size must be positive, got {pixel_nm}")
    if depth_nm <= 0 or cap_nm < 0:
        raise ValueError("depth must be positive and the cap non-negative")
    nan = float("nan")

    main = _fit_band(tip, pixel_nm, cap_nm, cap_nm + depth_nm)
    if main.problem or not math.isfinite(main.sphere_nm):
        return ApexRadius(
            radius_nm=nan,
            uncertainty_nm=nan,
            depth_nm=depth_nm,
            cap_nm=cap_nm,
            sphere_nm=main.sphere_nm,
            paraboloid_nm=main.paraboloid_nm,
            components_nm={},
            n_points=main.n_points,
            determined=False,
            reason=main.problem,
        )

    radius = 0.5 * (main.sphere_nm + main.paraboloid_nm)
    model = 0.5 * abs(main.sphere_nm - main.paraboloid_nm)
    # The paraboloid's standard error, carried to the mean by proportion: both
    # fits read the same curvature from the same pixels.
    statistical = radius * main.paraboloid_se_nm / main.paraboloid_nm
    at_depths = [radius]
    for factor in (0.5, 1.5):
        other = _fit_band(tip, pixel_nm, cap_nm, cap_nm + factor * depth_nm)
        if not other.problem and math.isfinite(other.sphere_nm):
            at_depths.append(0.5 * (other.sphere_nm + other.paraboloid_nm))
    spread = 0.5 * (max(at_depths) - min(at_depths))
    components = {"model": model, "statistical": statistical, "depth": spread}
    return ApexRadius(
        radius_nm=radius,
        uncertainty_nm=math.sqrt(sum(v**2 for v in components.values())),
        depth_nm=depth_nm,
        cap_nm=cap_nm,
        sphere_nm=main.sphere_nm,
        paraboloid_nm=main.paraboloid_nm,
        components_nm=components,
        n_points=main.n_points,
        determined=True,
    )


# ------------------------------------------------------------ tip estimates


@dataclass(frozen=True)
class TipEstimate:
    """A reconstructed tip: an outer bound on the real one, never sharper.

    `heights_nm` follows the module's convention (apex up, 0 at the centre).
    It is an upper bound on the true tip at every offset -- provided
    `threshold_nm` exceeds the noise differences it met -- so every width
    corrected with it is corrected by at most the right amount.

    `rim_depth_nm` is how far below the apex the *shallowest* pixel on the
    array's rim lies. A tip the image constrained closes inside its array and
    this is large; a tip it did not stays near zero somewhere on the rim, and
    `informative` is False. That is the flag a featureless image raises.
    """

    heights_nm: np.ndarray
    pixel_nm: float
    method: str  # "blind" | "known_surface"
    threshold_nm: float
    iterations: int
    points_used: int
    converged: bool
    rim_depth_nm: float
    informative: bool
    note: str = ""

    @property
    def size_px(self) -> int:
        return int(self.heights_nm.shape[0])

    def apex_radius(self, depth_nm: float = APEX_DEPTH_NM) -> ApexRadius:
        """`apex_radius` with the cap set to this estimate's noise threshold."""
        return apex_radius(
            self.heights_nm, self.pixel_nm, depth_nm=depth_nm, cap_nm=self.threshold_nm
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "pixel_nm": self.pixel_nm,
            "size_px": self.size_px,
            "threshold_nm": self.threshold_nm,
            "iterations": self.iterations,
            "points_used": self.points_used,
            "converged": self.converged,
            "rim_depth_nm": round(self.rim_depth_nm, 3),
            "informative": self.informative,
            "bound": "outer: never sharper than the true tip",
            "note": self.note,
            "heights_nm": np.round(self.heights_nm, 3).tolist(),
        }


def _rim_depth(tip: np.ndarray) -> float:
    rim = np.concatenate([tip[0, :], tip[-1, :], tip[:, 0], tip[:, -1]])
    return float(-rim.max()) + 0.0  # + 0.0 turns -0.0 into 0.0


def _informative(rim_depth_nm: float, threshold_nm: float) -> bool:
    return rim_depth_nm > RIM_THRESHOLDS * max(threshold_nm, _EPS)


def blind_tip(
    image: HeightMap,
    size_px: int,
    threshold_nm: float,
    *,
    max_iterations: int = MAX_ITERATIONS,
    contact_budget: int = CONTACT_BUDGET,
    points: str = "maxima",
) -> TipEstimate:
    """Villarrubia's blind estimate of the tip, from one image alone.

    `size_px` is the side of the tip array (odd), and the estimate is only
    of the tip within it. `threshold_nm` is the noise tolerance: set it to
    `THRESHOLD_SIGMA` times the image's pixel noise, or 0 for a noise-free
    image. The
    image must be flattened first: a tilt is a slope the tip is fitted to.
    See the module docstring for the algorithm, and for the cuts that make it
    fast without losing the outer-bound guarantee. `points="all"` drops the
    restriction to local maxima: a bound at least as tight, at tens of times
    the cost.

    `converged` is False when `max_iterations` ran out before a full pass over
    every useful point changed nothing. The estimate is still an outer bound
    then, only possibly a looser one, and in practice at the rim: the apex is
    fixed by the sharpest features, which are processed first.
    """
    a = _check_size(size_px)
    if threshold_nm < 0:
        raise ValueError(f"threshold must be non-negative, got {threshold_nm}")
    heights = np.asarray(image.heights_nm, dtype=float)
    rows, cols = heights.shape
    if rows < 4 * a + 2 or cols < 4 * a + 2:
        raise ValueError(f"image {heights.shape} is too small for a {size_px} px tip")
    tol = max(threshold_nm, _EPS)
    tip = np.zeros((size_px, size_px))
    # stack[i, j] is the tip-sized block of the image whose corner is (i, j).
    # Every image block the refinement needs is one of these, reversed.
    stack = sliding_window_view(heights, (size_px, size_px))
    inner = (slice(2 * a, rows - 2 * a), slice(2 * a, cols - 2 * a))
    uses = np.zeros(heights.shape, dtype=np.int64)
    tried = np.zeros(heights.shape, dtype=bool)
    if points == "maxima":
        around = sliding_window_view(np.pad(heights, 1, constant_values=-np.inf), (3, 3))
        eligible = heights >= around.max(axis=(2, 3))
    elif points == "all":
        eligible = np.ones(heights.shape, dtype=bool)
    else:
        raise ValueError(f"points must be 'maxima' or 'all', got {points!r}")
    iterations = 0
    converged = False

    while iterations < max_iterations:
        iterations += 1
        # The w = 0 test for every point at once: one erosion.
        eroded = erode(heights, tip)
        below = (eroded[inner] < heights[inner] - tol - _EPS) & eligible[inner]
        useful = np.argwhere(below) + 2 * a
        if len(useful) == 0:
            converged = True
            break
        counts = np.empty(len(useful), dtype=np.int64)
        for start in range(0, len(useful), _CHUNK):
            r, c = useful[start : start + _CHUNK].T
            h = heights[r, c][:, None, None]
            admitted = (h - stack[r - a, c - a]) <= tip + tol
            counts[start : start + len(r)] = admitted.sum(axis=(1, 2))
        order = np.lexsort((counts, uses[useful[:, 0], useful[:, 1]]))
        within = np.cumsum(counts[order]) <= contact_budget
        within[0] = True  # always make progress
        chosen = useful[order[within]]
        uses[chosen[:, 0], chosen[:, 1]] += 1

        before = tip.copy()
        for start in range(0, len(chosen), _CHUNK):
            r, c = chosen[start : start + _CHUNK].T
            h = heights[r, c][:, None, None]
            contact = (h - stack[r - a, c - a]) <= tip + tol
            bound = np.full((len(r), size_px, size_px), -np.inf)
            for p in range(size_px):
                for q in range(size_px):
                    who = np.flatnonzero(contact[:, p, q])
                    if who.size == 0:
                        continue
                    # I(x + w - d) over every d, for w = (p - a, q - a).
                    block = stack[r[who] + p - 2 * a, c[who] + q - 2 * a][:, ::-1, ::-1]
                    bound[who] = np.maximum(bound[who], block + tip[p, q])
            tip = np.minimum(tip, (bound - h + tol).min(axis=0))
            tip[a, a] = 0.0
        # Converged when a pass changes nothing and every point that could
        # still lower the tip has been tried against the tip as it now is.
        if bool((before - tip).max() > _EPS):
            tried[:] = False
        else:
            tried[chosen[:, 0], chosen[:, 1]] = True
            if bool(tried[useful[:, 0], useful[:, 1]].all()):
                converged = True
                break

    rim = _rim_depth(tip)
    informative = _informative(rim, threshold_nm)
    note = (
        ""
        if informative
        else "the image did not constrain the tip: no feature in it is sharper than the "
        "tip, so the estimate stayed flat on part of its rim. Image sharper features, or "
        "supply the geometry and use known_surface_tip"
    )
    return TipEstimate(
        heights_nm=tip,
        pixel_nm=image.pixel_nm,
        method="blind",
        threshold_nm=threshold_nm,
        iterations=iterations,
        points_used=int((uses > 0).sum()),
        converged=converged,
        rim_depth_nm=rim,
        informative=informative,
        note=note,
    )


def known_surface_tip(
    image: HeightMap,
    surface: np.ndarray,
    *,
    size_px: int,
    threshold_nm: float = 0.0,
) -> TipEstimate:
    """The bluntest tip consistent with an image of a surface of known shape.

    Every tip satisfying I = s dilated by t obeys t(v) <= I(x) - s(x + v) at
    every x, so the pointwise least of those bounds,

        t*(v) = min_x [ I(x) - s(x + v) ],

    is the largest consistent tip, an outer bound on the real one, and itself
    reproduces the image exactly when the model holds. This is the route for
    a reference whose geometry is given -- a block staircase, whose flat tops
    tell the blind estimate nothing, constrains the tip here down to its
    tallest step.

    `surface` must be registered to the image: same shape, same pixels, no
    lateral offset. Any vertical offset between the two is removed by setting
    the apex to zero. `threshold_nm` raises the result by that much (clipped
    at the apex) to keep it an outer bound under noise, as for `blind_tip`.
    """
    a = _check_size(size_px)
    heights = np.asarray(image.heights_nm, dtype=float)
    surf = np.asarray(surface, dtype=float)
    if surf.shape != heights.shape:
        raise ValueError(f"surface {surf.shape} and image {heights.shape} must be registered")
    if threshold_nm < 0:
        raise ValueError(f"threshold must be non-negative, got {threshold_nm}")
    rows, cols = heights.shape
    bound = np.full((size_px, size_px), np.inf)
    for i in range(size_px):
        for j in range(size_px):
            vi, vj = i - a, j - a
            r0, r1 = max(0, -vi), min(rows, rows - vi)
            c0, c1 = max(0, -vj), min(cols, cols - vj)
            if r1 <= r0 or c1 <= c0:
                continue
            diff = heights[r0:r1, c0:c1] - surf[r0 + vi : r1 + vi, c0 + vj : c1 + vj]
            bound[i, j] = float(diff.min())
    tip = np.minimum(bound - bound[a, a] + threshold_nm, 0.0)
    tip[a, a] = 0.0
    rim = _rim_depth(tip)
    informative = _informative(rim, threshold_nm)
    return TipEstimate(
        heights_nm=tip,
        pixel_nm=image.pixel_nm,
        method="known_surface",
        threshold_nm=threshold_nm,
        iterations=1,
        points_used=int(heights.size),
        converged=True,
        rim_depth_nm=rim,
        informative=informative,
        note="" if informative else "the surface did not constrain the tip across its array",
    )

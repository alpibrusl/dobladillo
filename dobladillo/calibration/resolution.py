"""Lateral resolution: how close two features can be and still be seen as two.

"Resolution" is quoted for AFMs as if it were a property of the instrument.
It is not. It depends on the tip, which blunts; on the noise, which decides
how shallow a dip between two features can be and still be believed; and on
the features themselves, because a tall pair leaves the tip more room to fall
between them than a low one. So it is computed here from all three, for the
features this project images: duplexes and hairpins about 2 nm tall.

**Criterion.** Two identical features of height h, a distance d apart, are
resolved when the image of the pair, made with this tip, dips between them by
more than k times the image noise. The resolution is the smallest such d.
That is the two-point criterion of C. Bustamante and D. Keller, "Scanning
force microscopy in biology", Physics Today 48(12), 32 (1995): for a
paraboloid tip of radius R and two point-like features, the dip Delta z is
reached at

    d = sqrt(2 R) (sqrt(Delta z) + sqrt(Delta z + Delta h)),

with Delta h the features' height difference (zero here), so d = sqrt(8 R Delta z).
Checked against the article's Box 1 on 2026-09-29 (#29): that is its equation,
valid for d > sqrt(2 R Delta h). Its first worked example (R = 10 nm, a 0.5 nm
dip, 6.4 nm) is this formula's 6.3 nm rounded; its second (a 2.0 nm height
difference, 12.5 nm) does not follow from its own equation, which gives
10.2 nm -- a slip in the example, not in the formula.
The formula takes the required dip as an input; setting it to k times the
image noise, with k = 3 by default, is the choice made here.

**The model.** The features are lines of circular cross-section, diameter h
-- a duplex lying on the surface, or a rung of a line ladder like the 6 nm
one on the commercial DNA-origami AFM reference -- parallel to one scan axis.
For a feature that does not vary along y, the image along x depends on the
tip only through its side profile, the highest point of the tip over each
column, so the problem is one-dimensional and exact: the image is the 1D
dilation of the pair by that profile. The tip is linearly interpolated
between its pixels. A pair of lines is the worst case for a given tip; two
dots are resolved at the same spacing or closer, because the tip's side
profile is the envelope of every section through it.

For a spherical tip of radius R and cylinders of radius a = h/2 there is a
closed form to check against: the image of one cylinder is a circle of radius
R + a about its axis, so the dip reaches Delta z at
d = 2 sqrt(2 (R + a) Delta z - Delta z^2). The tests hold the numerical
answer to it.

**Uncertainty.** A real tip is not round, so the resolution along the fast
axis differs from the one along the slow axis; both are reported, the value
is their mean and half their difference is one component of the
uncertainty. The other is the noise level's own uncertainty, carried through
by recomputing at the noise plus and minus it. A tip from `blind_tip` is an
outer bound, so a resolution computed from it is a *pessimistic* one: the
instrument resolves at least this well.

**Measured pairs.** `pair_resolved` asks the same question of a real
profile across a pair, but of a measured dip, which is noisy and reads deep;
it therefore asks for k times the dip's own uncertainty. Its docstring has
the numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from dobladillo.calibration.tip import tip_half_sizes
from dobladillo.constants import HELIX_DIAMETER_NM

#: A dip must exceed this many noise standard deviations to count. Chosen,
#: not derived: 3 sigma is the usual threshold for a one-off detection, and
#: the Bustamante-Keller formula takes the depth as an input.
DIP_SIGMA: Final = 3.0

#: Samples per nanometre of the fine grid the 1D dilation is evaluated on.
#: Chosen so the grid is far finer than any tip pixel.
_SAMPLES_PER_NM: Final = 50

#: Bisection steps on the spacing: 2^-40 of the search range.
_BISECTIONS: Final = 40


def bustamante_keller_nm(
    *, tip_radius_nm: float, dip_nm: float, height_step_nm: float = 0.0
) -> float:
    """The two-point resolution of a paraboloid tip, after Bustamante & Keller (1995).

    d = sqrt(2R) (sqrt(dz) + sqrt(dz + dh)): two point-like features whose
    heights differ by dh are resolved at spacing d when the dip is dz.
    """
    if tip_radius_nm <= 0 or dip_nm < 0 or height_step_nm < 0:
        raise ValueError("radius must be positive, dip and height step non-negative")
    return math.sqrt(2 * tip_radius_nm) * (math.sqrt(dip_nm) + math.sqrt(dip_nm + height_step_nm))


def _json(value: float, digits: int = 2) -> float | None:
    return round(value, digits) if math.isfinite(value) else None


@dataclass(frozen=True)
class Resolution:
    """The smallest resolvable spacing of two identical line features.

    `along_x_nm` is for lines parallel to the slow axis, imaged across the
    fast axis (the tip's profile over columns); `along_y_nm` for lines
    parallel to the fast axis. `value_nm` is their mean. When the answer is
    not determined -- the noise is larger than the features are tall, or the
    dip reaches the required depth only where the tip array has ended --
    `resolvable` is False, the value is infinite, and `reason` says why.
    """

    value_nm: float
    uncertainty_nm: float
    along_x_nm: float
    along_y_nm: float
    components_nm: dict[str, float]
    feature_height_nm: float
    noise_nm: float
    k: float
    resolvable: bool
    reason: str = ""

    @property
    def required_dip_nm(self) -> float:
        return self.k * self.noise_nm

    def as_dict(self) -> dict[str, Any]:
        return {
            "value_nm": _json(self.value_nm),
            "uncertainty_nm": _json(self.uncertainty_nm),
            "along_x_nm": _json(self.along_x_nm),
            "along_y_nm": _json(self.along_y_nm),
            "components_nm": {k: _json(v, 3) for k, v in self.components_nm.items()},
            "feature_height_nm": self.feature_height_nm,
            "noise_nm": self.noise_nm,
            "k": self.k,
            "required_dip_nm": round(self.required_dip_nm, 4),
            "criterion": (
                "two parallel lines of circular cross-section, diameter feature_height_nm, "
                "are resolved when the image dips between them by more than k * noise_nm"
            ),
            "resolvable": self.resolvable,
            "reason": self.reason,
        }


def _pair_dip(profile_u: np.ndarray, profile_t: np.ndarray, spacing: float, height: float) -> float:
    """How far the image of two lines dips below their tops, for one spacing.

    I(x) = max_u [ s(x + u) + P(u) ], evaluated for every x between the two
    axes; the tops image at exactly h (the apex rests on each top and P <= 0
    elsewhere), so the dip is h minus the lowest point between them.
    """
    radius = height / 2.0
    half = spacing / 2.0
    # Odd, so the midpoint -- where a symmetric tip's image is lowest -- is sampled.
    xs = np.linspace(-half, half, 2 * int(spacing * _SAMPLES_PER_NM / 8) + 3)
    pos = xs[:, None] + profile_u[None, :]

    def line(offset: np.ndarray) -> np.ndarray:
        inside = np.abs(offset) <= radius
        top = radius + np.sqrt(np.maximum(radius**2 - offset**2, 0.0))
        return np.where(inside, top, 0.0)

    surface = np.maximum(line(pos - half), line(pos + half))
    image = (surface + profile_t[None, :]).max(axis=1)
    return float(height - image.min())


def _axis_resolution(profile: np.ndarray, pixel_nm: float, height: float, dip: float) -> float:
    """Smallest spacing whose dip reaches `dip`, for one side profile of the tip.

    Beyond the array the profile is held at its edge value: the bluntest
    continuation of a tip that falls away from its apex, so the search can
    run past the array without inventing a sharper tip than was measured.
    Whether the answer leaned on that continuation is the caller's check.
    """
    half_px = len(profile) // 2
    reach = half_px * pixel_nm
    span = 2 * reach + height
    grid = np.linspace(-span, span, int(2 * span * _SAMPLES_PER_NM) + 1)
    finite = np.where(np.isfinite(profile), profile, -1e9)
    values = np.interp(grid, (np.arange(len(profile)) - half_px) * pixel_nm, finite)
    ceiling = 2 * reach
    if _pair_dip(grid, values, ceiling, height) < dip:
        return math.inf
    low, high = 0.0, ceiling
    for _ in range(_BISECTIONS):
        mid = 0.5 * (low + high)
        if _pair_dip(grid, values, mid, height) >= dip:
            high = mid
        else:
            low = mid
    return high


def lateral_resolution(
    tip: np.ndarray,
    pixel_nm: float,
    noise_nm: float,
    *,
    feature_height_nm: float = HELIX_DIAMETER_NM,
    k: float = DIP_SIGMA,
    noise_uncertainty_nm: float = 0.0,
) -> Resolution:
    """The resolution this tip and this noise allow, for features this tall.

    `tip` follows `calibration.tip`'s convention (apex up, 0 at the centre),
    on the image's pixel grid; a `TipEstimate`'s `heights_nm` is one. See the
    module docstring for the criterion and the model.
    """
    tip_half_sizes(tip)
    if pixel_nm <= 0 or noise_nm < 0 or feature_height_nm <= 0 or k <= 0:
        raise ValueError("pixel size, feature height and k must be positive; noise non-negative")
    dip = k * noise_nm
    nan = float("nan")

    def both(noise: float) -> tuple[float, float]:
        need = k * noise
        return (
            _axis_resolution(tip.max(axis=0), pixel_nm, feature_height_nm, need),
            _axis_resolution(tip.max(axis=1), pixel_nm, feature_height_nm, need),
        )

    if dip >= feature_height_nm:
        return Resolution(
            value_nm=math.inf,
            uncertainty_nm=nan,
            along_x_nm=math.inf,
            along_y_nm=math.inf,
            components_nm={},
            feature_height_nm=feature_height_nm,
            noise_nm=noise_nm,
            k=k,
            resolvable=False,
            reason=f"a {dip:.2f} nm dip is required, deeper than the {feature_height_nm} nm "
            "features are tall",
        )
    along_x, along_y = both(noise_nm)
    # Seen from the midpoint of the pair, the features lie up to d/2 + h/2
    # away; if that is past the array's edge, the answer came from the
    # continuation beyond it and not from the measured tip.
    reach = min(tip.shape) // 2 * pixel_nm
    if not max(along_x, along_y) / 2 + feature_height_nm / 2 <= reach:
        return Resolution(
            value_nm=math.inf,
            uncertainty_nm=nan,
            along_x_nm=along_x,
            along_y_nm=along_y,
            components_nm={},
            feature_height_nm=feature_height_nm,
            noise_nm=noise_nm,
            k=k,
            resolvable=False,
            reason="the dip reaches the required depth only past the edge of the tip "
            "array, so the array is too small to say; use a larger one",
        )
    value = 0.5 * (along_x + along_y)
    components = {"anisotropy": 0.5 * abs(along_x - along_y), "noise": 0.0}
    if noise_uncertainty_nm > 0:
        high_x, high_y = both(noise_nm + noise_uncertainty_nm)
        low_x, low_y = both(max(noise_nm - noise_uncertainty_nm, 0.0))
        components["noise"] = 0.25 * ((high_x + high_y) - (low_x + low_y))
    return Resolution(
        value_nm=value,
        uncertainty_nm=math.sqrt(sum(v**2 for v in components.values())),
        along_x_nm=along_x,
        along_y_nm=along_y,
        components_nm=components,
        feature_height_nm=feature_height_nm,
        noise_nm=noise_nm,
        k=k,
        resolvable=True,
    )


# ------------------------------------------------------------ measured pairs


@dataclass(frozen=True)
class PairResolution:
    """Whether a profile across a real pair of marks shows two, and how surely.

    `dip_nm` is the deepest valley between two peaks anywhere in the profile:
    the lower of the highest points on either side, minus the valley floor.
    Both peaks must stand above the profile's half height, so a valley
    between a feature and the substrate's noise does not count.
    Its uncertainty is the noise of a difference of two samples, sqrt(2)
    times the per-sample noise.

    `resolved` asks for a dip deeper than k times ITS OWN uncertainty, not k
    times the pixel noise as `lateral_resolution` does, and the difference is
    deliberate. The prediction is about the true, noise-free dip. A measured
    dip is the highest samples minus the lowest one, picked out of noise, so
    it reads deep: on pairs rendered through a known tip, a threshold of
    k sigma called 71-96% of single scan lines resolved at exactly the
    predicted spacing and 12-26% at half of it. At k sqrt(2) sigma the same
    lines give 25-53% at the predicted spacing -- about the even odds a
    threshold should give there -- 100% at one and a half times it, and at
    most 3% at half.
    """

    resolved: bool
    dip_nm: float
    dip_uncertainty_nm: float
    noise_nm: float
    k: float
    peaks_px: tuple[int, int]
    valley_px: int
    separation_nm: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "dip_nm": round(self.dip_nm, 4),
            "dip_uncertainty_nm": round(self.dip_uncertainty_nm, 4),
            "noise_nm": self.noise_nm,
            "k": self.k,
            "peaks_px": list(self.peaks_px),
            "valley_px": self.valley_px,
            "separation_nm": None if self.separation_nm is None else round(self.separation_nm, 2),
        }


def pair_resolved(
    profile: np.ndarray,
    noise_nm: float,
    *,
    k: float = DIP_SIGMA,
    pixel_nm: float | None = None,
) -> PairResolution:
    """The empirical test: does this line profile across a pair show a dip?

    For when a pair of marks at a known spacing has actually been imaged --
    the rungs of a line ladder, two hairpins placed a known distance apart.
    `noise_nm` is the per-sample noise of the profile *as passed*: if it was
    averaged over n scan lines, that is the image noise over sqrt(n).
    """
    values = np.asarray(profile, dtype=float)
    if values.ndim != 1 or len(values) < 3:
        raise ValueError("a profile is a 1D array of at least three samples")
    if noise_nm < 0 or k <= 0:
        raise ValueError("noise must be non-negative and k positive")
    left = np.maximum.accumulate(values)
    right = np.maximum.accumulate(values[::-1])[::-1]
    shoulders = np.minimum(left[:-2], right[2:])
    half = 0.5 * (float(values.min()) + float(values.max()))
    # Only valleys between two peaks that each stand above half height:
    # otherwise the noise on the substrate beside a single feature is a
    # "valley" between the feature and a noise spike.
    dips = np.where(shoulders >= half, shoulders - values[1:-1], -np.inf)
    valley = int(np.argmax(dips)) + 1
    dip = max(float(dips[valley - 1]), 0.0)
    first = int(np.argmax(values[:valley]))
    second = valley + 1 + int(np.argmax(values[valley + 1 :]))
    return PairResolution(
        resolved=dip > k * math.sqrt(2.0) * noise_nm,
        dip_nm=dip,
        dip_uncertainty_nm=math.sqrt(2.0) * noise_nm,
        noise_nm=noise_nm,
        k=k,
        peaks_px=(first, second),
        valley_px=valley,
        separation_nm=None if pixel_nm is None else (second - first) * pixel_nm,
    )


# ------------------------------------------------------------------ noise


@dataclass(frozen=True)
class Noise:
    """Pixel noise of an image, from differences of neighbouring pixels."""

    sigma_nm: float
    uncertainty_nm: float
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sigma_nm": round(self.sigma_nm, 4),
            "uncertainty_nm": round(self.uncertainty_nm, 4),
            "n": self.n,
            "method": "MAD of fast-axis second differences / (0.6745 sqrt 6)",
        }


def pixel_noise(heights: np.ndarray) -> Noise:
    """White pixel noise, robust to the features, their slopes and line offsets.

    Second differences along the fast axis, h[x+1] - 2 h[x] + h[x-1], cancel
    every line's own offset AND any locally linear slope, and leave sqrt(6)
    times the pixel noise. First differences, used until #31, cancel offsets
    but not slopes: on a scan crowded with tall features most neighbour pairs
    lie on a flank, and the estimate read 0.42 nm for a true 0.05 nm, which
    set the tip threshold eight times too high. A tip-shaped flank is curved,
    not straight, but its curvature is nearly constant, and the median
    absolute deviation ignores a constant: measured, 0.052-0.060 nm for a true
    0.05 on sparse to very crowded fields, 0.205-0.218 for 0.20. The residual
    is an OVERestimate, which only blunts the reconstructed tip -- the safe
    side for an outer bound.

    0.6745 converts a MAD to a standard deviation for a normal distribution.
    The uncertainty is approximate: the normal standard error of a standard
    deviation, sigma / sqrt(2 (n - 1)), times 1.65 for the MAD's lower
    efficiency, ignoring that neighbouring second differences share pixels.
    """
    values = np.asarray(heights, dtype=float)
    if values.ndim != 2 or values.shape[1] < 3:
        raise ValueError("expected a 2D image at least three pixels wide")
    second = (values[:, 2:] - 2.0 * values[:, 1:-1] + values[:, :-2]).ravel()
    mad = float(np.median(np.abs(second - np.median(second))))
    sigma = mad / 0.6745 / math.sqrt(6.0)
    n = len(second)
    return Noise(sigma_nm=sigma, uncertainty_nm=1.65 * sigma / math.sqrt(2 * (n - 1)), n=n)

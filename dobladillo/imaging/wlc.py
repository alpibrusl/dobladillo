"""Stiff rods on a surface: what thermal bending looks like, and what a built-in arc does.

A six-helix bundle is stiff -- a persistence length in microns against its
~400 nm length -- but not rigid. Adsorbed on mica it will not lie as a ruler.
So "is the bundle straight?" cannot be answered by looking for bent particles:
every particle is a little bent. It is answered by asking whether the
bending is the kind thermal fluctuation makes or the kind a design makes.

**The model.** A wormlike chain equilibrated in two dimensions. Along the
backbone the tangent angle theta(s) performs a random walk: the angle
difference over an arc length s is Gaussian with

    < (theta(s0 + s) - theta(s0))^2 > = s / Lp            (2D wormlike chain)

because the bending energy (kT Lp / 2) * integral of curvature^2 gives each
independent increment d(theta) a variance ds / Lp. From it follow the
tangent correlation <cos d(theta)> = exp(-s / 2Lp) and the mean-square
end-to-end distance of a chain of contour L,

    <R^2> = 4 Lp L [1 - (2 Lp / L)(1 - exp(-L / 2Lp))].

**A built-in arc** of curvature kappa0 adds a deterministic turn, so

    < d(theta)^2 > = s / Lp + kappa0^2 s^2.

That is the whole discriminator, and it is why the fit below has a quadratic
term: thermal bending grows the angle variance linearly with separation, a
systematic arc grows it quadratically. The sign of kappa0 drops out -- a
curved rod can land on the mica bent either way, and the square does not care
-- so a population of arcs landing at random is still distinguishable from a
straight one. An arc landing with its bend out of the surface plane would be
pressed flat and hidden; that is a limit of the method, stated in the
experiment's protocol rather than modelled here.

**2D-equilibrated or kinetically trapped?** A chain that lands and freezes is a
projection of a 3D conformation, not an equilibrated 2D one. For a stiff rod
(L well below Lp) the two agree to leading order: in 3D each of the two
transverse components of the tangent deviation has variance s / Lp, and the
component in the image plane is exactly the 2D result. Beyond small angles
they differ, which is why this module is used only where L / Lp < 1.

This module knows nothing about DNA or about images. It takes lengths and
angles and returns statistics; `imaging.rods` makes the angles from a scan.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Bootstrap resamples for every interval here. Fixed-seeded, so a result is
#: reproducible run to run; enough that the 2.5th percentile is stable to a
#: few per cent.
BOOTSTRAP = 2000


# ---------------------------------------------------------------- the model


def mean_square_end_to_end_2d(contour_nm: float, lp_nm: float) -> float:
    """<R^2> of a 2D wormlike chain, nm^2. Tends to L^2 as Lp grows."""
    if contour_nm <= 0 or lp_nm <= 0:
        raise ValueError("contour and persistence length must be positive")
    x = contour_nm / (2.0 * lp_nm)
    # -expm1(-x) is 1 - exp(-x) without cancellation for a stiff chain, where
    # x is small and the naive form loses every significant figure.
    return 4.0 * lp_nm * contour_nm * (1.0 - (-math.expm1(-x)) / x)


def tangent_msd(s_nm: np.ndarray | float, lp_nm: float, curvature_per_nm: float = 0.0) -> Any:
    """<d(theta)^2> at separation s: s / Lp, plus (kappa0 s)^2 for a built-in arc."""
    s = np.asarray(s_nm, dtype=float)
    return s / lp_nm + (curvature_per_nm * s) ** 2


@dataclass(frozen=True)
class Arc:
    """A circular arc of a given contour: what a rod curved by design looks like."""

    contour_nm: float
    radius_nm: float

    @property
    def turning_rad(self) -> float:
        return self.contour_nm / self.radius_nm

    @property
    def end_to_end_ratio(self) -> float:
        half = self.turning_rad / 2.0
        return math.sin(half) / half

    @property
    def sagitta_nm(self) -> float:
        return self.radius_nm * (1.0 - math.cos(self.turning_rad / 2.0))

    def as_dict(self) -> dict[str, Any]:
        return {
            "contour_nm": round(self.contour_nm, 1),
            "radius_nm": round(self.radius_nm, 1),
            "turning_deg": round(math.degrees(self.turning_rad), 1),
            "end_to_end_ratio": round(self.end_to_end_ratio, 4),
            "sagitta_nm": round(self.sagitta_nm, 1),
        }


def sample_shapes(
    n: int,
    *,
    contour_nm: float,
    lp_nm: float,
    curvature_per_nm: float = 0.0,
    ds_nm: float = 2.0,
    seed: int = 0,
) -> list[np.ndarray]:
    """`n` backbones drawn from a 2D wormlike chain, optionally with a built-in arc.

    Each is an (m, 2) array of points in nm, starting at the origin along a
    random direction. A built-in arc bends each rod one way or the other at
    random, as a curved rod landing on either face would.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    rng = np.random.default_rng(seed)
    steps = max(2, round(contour_nm / ds_nm))
    ds = contour_nm / steps
    shapes = []
    for _ in range(n):
        sign = rng.choice((-1.0, 1.0))
        increments = rng.normal(sign * curvature_per_nm * ds, math.sqrt(ds / lp_nm), steps)
        theta = rng.uniform(0, 2 * math.pi) + np.concatenate([[0.0], np.cumsum(increments)])
        # Midpoint headings, so the chord of each step bisects its two ends.
        heading = 0.5 * (theta[:-1] + theta[1:])
        steps_xy = ds * np.column_stack([np.cos(heading), np.sin(heading)])
        shapes.append(np.vstack([[0.0, 0.0], np.cumsum(steps_xy, axis=0)]))
    return shapes


def contour_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def end_to_end(points: np.ndarray) -> float:
    return float(np.linalg.norm(points[-1] - points[0]))


def sagitta(points: np.ndarray) -> float:
    """Largest distance of the backbone from its end-to-end chord, nm."""
    chord = points[-1] - points[0]
    length = float(np.linalg.norm(chord))
    if length == 0:
        return 0.0
    offsets = points - points[0]
    cross = offsets[:, 0] * chord[1] - offsets[:, 1] * chord[0]
    return float(np.abs(cross).max() / length)


def tangent_angles(points: np.ndarray) -> np.ndarray:
    """Unwrapped heading of each segment, radians."""
    d = np.diff(points, axis=0)
    return np.unwrap(np.arctan2(d[:, 1], d[:, 0]))


def resample(points: np.ndarray, ds_nm: float) -> np.ndarray:
    """The same curve at uniform arc-length spacing `ds_nm`, ends kept."""
    segment = np.linalg.norm(np.diff(points, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(segment)])
    if arc[-1] <= 0:
        return points[:1].copy()
    count = max(2, round(arc[-1] / ds_nm) + 1)
    targets = np.linspace(0.0, arc[-1], count)
    return np.column_stack(
        [np.interp(targets, arc, points[:, 0]), np.interp(targets, arc, points[:, 1])]
    )


def _quantiles(values: np.ndarray) -> dict[str, float]:
    p = np.percentile(values, [2.5, 25, 50, 75, 97.5])
    return {
        "p2.5": round(float(p[0]), 4),
        "p25": round(float(p[1]), 4),
        "median": round(float(p[2]), 4),
        "p75": round(float(p[3]), 4),
        "p97.5": round(float(p[4]), 4),
        "mean": round(float(values.mean()), 4),
    }


def population_statistics(shapes: Sequence[np.ndarray]) -> dict[str, Any]:
    """Distribution of end-to-end/contour and sagitta/contour over a population."""
    ratios = np.array([end_to_end(p) / contour_length(p) for p in shapes])
    sags = np.array([sagitta(p) / contour_length(p) for p in shapes])
    return {
        "n": len(shapes),
        "end_to_end_ratio": _quantiles(ratios),
        "sagitta_over_contour": _quantiles(sags),
    }


# ------------------------------------------------------------ the estimators


def _msd_table(
    angle_series: Sequence[np.ndarray], lags: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per molecule, the sum of squared angle differences and their count at each lag."""
    sums = np.zeros((len(angle_series), lags.size))
    counts = np.zeros((len(angle_series), lags.size))
    for m, theta in enumerate(angle_series):
        for k, lag in enumerate(lags):
            if lag < theta.size:
                d = theta[lag:] - theta[:-lag]
                sums[m, k] = float(np.dot(d, d))
                counts[m, k] = d.size
    return sums, counts


@dataclass(frozen=True)
class TangentFit:
    """<d(theta)^2>(s) = c + s / Lp + kappa0^2 s^2, fitted over a population.

    `c` absorbs tracing noise: an angle measured with error sigma adds 2 sigma^2
    at every separation longer than the smoothing, so it is a constant, not a
    slope. Every interval is a bootstrap over molecules, never over points,
    because points along one molecule are not independent.
    """

    n_molecules: int
    s_range_nm: tuple[float, float]
    intercept_rad2: float
    slope_per_nm: float
    slope_ci95: tuple[float, float]
    quadratic_per_nm2: float
    quadratic_ci95: tuple[float, float]
    #: Lp from the linear-only fit, used when no arc is detected: with the
    #: quadratic term free, the slope is less well determined than it need be.
    straight_slope_per_nm: float
    straight_slope_ci95: tuple[float, float]

    @property
    def systematically_curved(self) -> bool:
        """The quadratic term's whole 95% interval is above zero."""
        return self.quadratic_ci95[0] > 0

    @staticmethod
    def _lp(slope: float) -> float:
        return 1.0 / slope if slope > 0 else math.inf

    @property
    def lp_nm(self) -> float:
        slope = self.slope_per_nm if self.systematically_curved else self.straight_slope_per_nm
        return self._lp(slope)

    @property
    def lp_ci95_nm(self) -> tuple[float, float]:
        low, high = self.slope_ci95 if self.systematically_curved else self.straight_slope_ci95
        return (self._lp(high), self._lp(low))

    @property
    def curvature_per_nm(self) -> float:
        return math.sqrt(max(self.quadratic_per_nm2, 0.0))

    @property
    def curvature_ci95_per_nm(self) -> tuple[float, float]:
        low, high = self.quadratic_ci95
        return (math.sqrt(max(low, 0.0)), math.sqrt(max(high, 0.0)))

    @property
    def verdict(self) -> str:
        if self.systematically_curved:
            low, high = self.curvature_ci95_per_nm
            return (
                f"systematically curved: intrinsic radius {1 / high:.0f}-"
                f"{(1 / low) if low > 0 else math.inf:.0f} nm (95%)"
            )
        high = self.curvature_ci95_per_nm[1]
        bound = f"{1 / high:.0f} nm" if high > 0 else "unbounded"
        return f"no systematic curvature detected: any intrinsic radius is above {bound} (95%)"

    def as_dict(self) -> dict[str, Any]:
        def r(v: float) -> float | None:
            return None if math.isinf(v) else round(v, 1)

        return {
            "model": "<dtheta^2>(s) = c + s/Lp + kappa0^2 s^2: "
            "2D wormlike chain plus a built-in arc",
            "n_molecules": self.n_molecules,
            "s_range_nm": [round(v, 1) for v in self.s_range_nm],
            "intercept_rad2": round(self.intercept_rad2, 5),
            "slope_per_nm": self.slope_per_nm,
            "slope_ci95": list(self.slope_ci95),
            "quadratic_per_nm2": self.quadratic_per_nm2,
            "quadratic_ci95": list(self.quadratic_ci95),
            "systematically_curved": self.systematically_curved,
            "persistence_length_nm": r(self.lp_nm),
            "persistence_length_ci95_nm": [r(v) for v in self.lp_ci95_nm],
            "persistence_length_from": "full fit"
            if self.systematically_curved
            else "linear fit (no arc detected)",
            "intrinsic_curvature_per_nm": self.curvature_per_nm,
            "intrinsic_curvature_ci95_per_nm": list(self.curvature_ci95_per_nm),
            "verdict": self.verdict,
            "interval": f"bootstrap over molecules, {BOOTSTRAP} resamples",
        }


def fit_tangent_msd(
    angle_series: Sequence[np.ndarray],
    *,
    ds_nm: float,
    s_min_nm: float,
    s_max_nm: float,
    seed: int = 0,
) -> TangentFit:
    """Fit the tangent-angle variance against separation, with bootstrap intervals.

    `angle_series` are unwrapped tangent angles at uniform spacing `ds_nm`,
    one array per molecule. Lags run from `s_min_nm` -- beyond the tracing's
    smoothing, where the noise is a constant -- to `s_max_nm`, which should
    stay below the shorter molecules' length so that the longest lags are not
    averaged over a handful of molecules.
    """
    usable = [np.asarray(a, dtype=float) for a in angle_series if len(a) > 2]
    if len(usable) < 3:
        raise ValueError(f"need at least 3 traced molecules, got {len(usable)}")
    first = max(1, math.ceil(s_min_nm / ds_nm))
    last = max(first + 2, math.floor(s_max_nm / ds_nm))
    lags = np.arange(first, last + 1)
    s = lags * ds_nm
    sums, counts = _msd_table(usable, lags)
    keep = counts.sum(axis=0) > 0
    lags, s, sums, counts = lags[keep], s[keep], sums[:, keep], counts[:, keep]
    if s.size < 3:
        raise ValueError("too few separations to fit; molecules shorter than s_min")

    # Scaled so the normal equations are well conditioned: s in units of the
    # longest lag.
    scale = float(s.max())
    u = s / scale
    full = np.linalg.pinv(np.column_stack([np.ones_like(u), u, u**2]))
    linear = np.linalg.pinv(np.column_stack([np.ones_like(u), u]))

    def fit(total: np.ndarray, count: np.ndarray) -> tuple[float, float, float, float]:
        with np.errstate(invalid="ignore", divide="ignore"):
            y = np.where(count > 0, total / np.maximum(count, 1), np.nan)
        if np.isnan(y).any():
            # A resample that lost every molecule reaching a lag: fit the rest.
            ok = ~np.isnan(y)
            c, a, b = np.linalg.lstsq(
                np.column_stack([np.ones(ok.sum()), u[ok], u[ok] ** 2]), y[ok], rcond=None
            )[0]
            c2, a2 = np.linalg.lstsq(
                np.column_stack([np.ones(ok.sum()), u[ok]]), y[ok], rcond=None
            )[0]
        else:
            c, a, b = full @ y
            c2, a2 = linear @ y
        return float(c), float(a / scale), float(b / scale**2), float(a2 / scale)

    c, a, b, a_lin = fit(sums.sum(axis=0), counts.sum(axis=0))
    rng = np.random.default_rng(seed)
    draws = np.empty((BOOTSTRAP, 3))
    m = len(usable)
    for i in range(BOOTSTRAP):
        pick = rng.integers(0, m, m)
        _, da, db, dlin = fit(sums[pick].sum(axis=0), counts[pick].sum(axis=0))
        draws[i] = (da, db, dlin)
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return TangentFit(
        n_molecules=m,
        s_range_nm=(float(s.min()), float(s.max())),
        intercept_rad2=c,
        slope_per_nm=a,
        slope_ci95=(float(lo[0]), float(hi[0])),
        quadratic_per_nm2=b,
        quadratic_ci95=(float(lo[1]), float(hi[1])),
        straight_slope_per_nm=a_lin,
        straight_slope_ci95=(float(lo[2]), float(hi[2])),
    )


def _mean_ratio_sq(contours: np.ndarray, lp: float) -> float:
    return float(np.mean([mean_square_end_to_end_2d(L, lp) / L**2 for L in contours]))


def _invert_end_to_end(contours: np.ndarray, observed: float) -> float:
    """The Lp at which the model's mean R^2/L^2 equals `observed`. Monotonic in Lp."""
    if observed >= 1.0:
        return math.inf
    low, high = 1e-3, 1e9
    if _mean_ratio_sq(contours, low) > observed:
        return low
    for _ in range(200):
        mid = math.sqrt(low * high)
        if _mean_ratio_sq(contours, mid) < observed:
            low = mid
        else:
            high = mid
        if high / low < 1 + 1e-6:
            break
    return math.sqrt(low * high)


def lp_from_end_to_end(
    contours_nm: Sequence[float], end_to_ends_nm: Sequence[float], *, seed: int = 0
) -> dict[str, Any]:
    """Lp from the mean R^2 / L^2, each molecule at its own contour length.

    Assumes no built-in arc: an arc shortens R as bending does, so on a curved
    population this Lp comes out too LOW, and disagreeing with the tangent
    fit's Lp is itself evidence of an arc. Coarse for a stiff rod -- R/L sits
    near 1 and the information is in how far below it -- which is why the
    tangent fit is the primary estimate and this one the cross-check.
    """
    contours = np.asarray(contours_nm, dtype=float)
    ratios = (np.asarray(end_to_ends_nm, dtype=float) / contours) ** 2
    if contours.size < 3:
        raise ValueError(f"need at least 3 molecules, got {contours.size}")
    estimate = _invert_end_to_end(contours, float(ratios.mean()))
    rng = np.random.default_rng(seed)
    # Fewer resamples than the tangent fit: each inversion is a bisection.
    boots = []
    for _ in range(BOOTSTRAP // 4):
        pick = rng.integers(0, contours.size, contours.size)
        boots.append(_invert_end_to_end(contours[pick], float(ratios[pick].mean())))
    # A resample whose rods are all straight has Lp = inf; percentiles of a
    # list holding inf interpolate to nan, so take order statistics instead.
    low, high = np.percentile(boots, [2.5, 97.5], method="nearest")

    def r(v: float) -> float | None:
        return None if math.isinf(v) else round(float(v), 1)

    return {
        "model": "<R^2> = 4 Lp L [1 - (2Lp/L)(1 - exp(-L/2Lp))], 2D wormlike chain, no arc",
        "n_molecules": int(contours.size),
        "mean_end_to_end_ratio_sq": round(float(ratios.mean()), 5),
        "persistence_length_nm": r(estimate),
        "persistence_length_ci95_nm": [r(low), r(high)],
        "interval": f"bootstrap over molecules, {BOOTSTRAP // 4} resamples",
    }

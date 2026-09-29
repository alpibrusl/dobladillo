"""Synthetic scans of calibration tiles, with the instrument's error written down.

The sibling of `synthetic_pattern`, for `calibration.lateral`. Sheets carrying
marks land at random angles, positions and ways round, and the scan is then
seen through a scanner that is WRONG by a known amount: its x and y scales
and its skew are imposed, and the fit must recover them. So must it recover
the object's own anisotropy -- the sheet drawn wider or narrower across its
helices than the nominal design, by a known factor -- because the real one
is not known either.

**Where the scanner acts.** A scanner error is a coordinate error: the tip
touches the real surface, and the instrument reports the wrong place for
it. So the surface is tip-dilated in TRUE coordinates and then placed where
the scanner says: each image pixel, at reported position p (nm, raster frame:
x along a line, y down the lines), shows the true surface at S^-1 p, with

    S = [[sx, k], [0, sy]],   k = sy tan(skew).

Tip shapes are therefore round in the sample and slightly elliptic in the
image, as they are on a real miscalibrated instrument. Every point is
evaluated analytically at its true position rather than rendered and then
resampled, so the warp adds no interpolation blur of its own.

**How a mark on a sheet is drawn.** The tip-dilated image of a union of
objects is the pointwise MAXIMUM of their dilated images (dilation commutes
with the maximum). So a hairpin is drawn as a bump whose top stands at the
sheet's height plus its own -- `synthetic_pattern`'s sphere-over-bump profile,
at absolute height -- and the result is max(sheet, marks). `synthetic_pattern`
ADDS a mark layer to the sheet instead, which is the same thing on the sheet's
plateau and not near its edge: there the sheet's tip ramp drops under the
mark and drags the mark's outer half down with it. A mark centroid then moves
inward by an amount that grows with the tip radius, and with marks two and a
half helices from the long edges, that is a tip-dependent scale error of the
very kind a centroid calibration exists to avoid. The maximum is the right
geometry, and it is what this module draws.

The sheet itself is `synthetic._stamp_rectangle`'s model -- a plateau whose
edges are the rigid-sphere ramp -- evaluated at arbitrary points.

This is a test instrument, not a simulator. It makes no claim about what a
real tile looks like on mica, how its hairpins stand, or what fraction lands
marks-up.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.pattern import TRANSFORMS, frame_axes
from dobladillo.imaging.synthetic import SHEET_HEIGHT_NM, _instrument
from dobladillo.imaging.synthetic_pattern import MARK_RADIUS_NM

__all__ = [
    "CalibrationScan",
    "PlacedTile",
    "ScannerTruth",
    "calibration_scan",
    "scanner_matrix",
]

#: Tries at placing each tile before giving up on it. Tiles that do not fit
#: are dropped, and the truth lists only the ones drawn.
PLACEMENT_TRIES: Final = 400

#: Tiles are spaced for a tip at least this blunt, nm. See `calibration_scan`.
PLACEMENT_TIP_NM: Final = 20.0


def scanner_matrix(scale_x: float, scale_y: float, skew_deg: float) -> np.ndarray:
    """S: true position (nm, raster frame) to reported position.

    Upper triangular, because any 2D linear map is an upper-triangular one
    times a rotation, and the rotation of a scanner relative to a sample that
    lands at random angles is not observable. Positive skew leans the imaged
    y axis towards +x: a line that is truly down the image comes out tilted
    by `skew_deg` towards increasing column.
    """
    return np.array([[scale_x, scale_y * math.tan(math.radians(skew_deg))], [0.0, scale_y]])


@dataclass(frozen=True)
class ScannerTruth:
    """What was imposed on the whole scan."""

    scale_x: float
    scale_y: float
    skew_deg: float
    anisotropy: float
    tip_radius_nm: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "skew_deg": self.skew_deg,
            "anisotropy": self.anisotropy,
            "tip_radius_nm": self.tip_radius_nm,
            "convention": "reported = S . true, S = [[scale_x, scale_y tan(skew)], [0, scale_y]]; "
            "anisotropy = drawn / nominal scale across the helices (object y)",
        }


@dataclass(frozen=True)
class PlacedTile:
    """One tile as drawn: where it appears in the image, which way round."""

    centre_px: tuple[float, float]  # (row, col) where the instrument reports the centre
    angle_deg: float  # in TRUE coordinates, as `imaging.pattern.frame_axes`
    transform: str
    shows: str  # "marks" | "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "centre_px": [round(v, 2) for v in self.centre_px],
            "angle_deg": round(self.angle_deg, 2),
            "transform": self.transform,
            "shows": self.shows,
        }


@dataclass(frozen=True)
class CalibrationScan:
    image: HeightMap
    truth: tuple[PlacedTile, ...]
    scanner: ScannerTruth


def _sheet_profile(
    along: np.ndarray,
    across: np.ndarray,
    *,
    half_length: float,
    half_width: float,
    height_nm: float,
    tip_radius_nm: float,
) -> np.ndarray:
    """`synthetic._stamp_rectangle`'s plateau with rigid-sphere edges, in nm."""

    def fraction(distance: np.ndarray, half: float) -> np.ndarray:
        outside = np.abs(distance) - half
        if tip_radius_nm <= 0:
            return (outside <= 0).astype(float)
        x = np.clip(outside, 0.0, tip_radius_nm)
        z = height_nm - tip_radius_nm + np.sqrt(np.maximum(tip_radius_nm**2 - x**2, 0.0))
        return np.clip(np.where(outside <= 0, height_nm, z) / height_nm, 0.0, 1.0)

    out: np.ndarray = height_nm * fraction(along, half_length) * fraction(across, half_width)
    return out


def calibration_scan(
    marks_nm: Sequence[tuple[float, float]],
    *,
    sheet_nm: tuple[float, float],
    n_tiles: int = 24,
    size_px: int = 768,
    scan_nm: float = 1100.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    skew_deg: float = 0.0,
    anisotropy: float = 1.0,
    tip_radius_nm: float = 10.0,
    height_nm: float = SHEET_HEIGHT_NM,
    mark_height_nm: float = 2.0,
    angles_deg: tuple[float, float] = (0.0, 180.0),
    transforms: Sequence[str] = tuple(TRANSFORMS),
    face_down_fraction: float = 0.0,
    missing_fraction: float = 0.0,
    noise_nm: float = 0.12,
    tilt_nm: float = 6.0,
    line_noise_nm: float = 0.25,
    seed: int = 0,
) -> CalibrationScan:
    """One scan of tiles seen through a known wrong scanner.

    `marks_nm` are the hairpins in the object frame (x along the helices,
    y across, seen from the marked face) at the NOMINAL geometry;
    `sheet_nm` the nominal outline. The object is drawn with its y scaled
    by `anisotropy`, both marks and outline. Each tile's angle is uniform
    in `angles_deg` and its transform drawn from `transforms`; a fraction
    lands face down (marks hidden, `shows="none"`), and a fraction of marks
    is knocked out at random on the others. Empty `marks_nm` draws plain
    rectangles: the negative control.
    """
    for name in transforms:
        if name not in TRANSFORMS:
            raise ValueError(f"unknown transform {name!r}")
    rng = np.random.default_rng(seed)
    pixel = scan_nm / size_px
    s = scanner_matrix(scale_x, scale_y, skew_deg)
    s_inv = np.linalg.inv(s)
    length, width = sheet_nm[0], sheet_nm[1] * anisotropy
    marks = np.array(marks_nm, dtype=float).reshape(-1, 2)
    bump = tip_radius_nm + MARK_RADIUS_NM
    top = height_nm + mark_height_nm

    # A tile and its tip skirt fit in a circle of half its diagonal plus the
    # skirt, in true nm; the scanner can stretch that by its largest singular
    # value. Circles apart and inside the frame: no merged tiles, none cut.
    # The skirt is sized for the blunter of this tip and PLACEMENT_TIP_NM, so
    # that up to that radius the same seed places the same tiles whatever the
    # tip: the tests image one set of tiles with two tips and compare.
    reach = max(tip_radius_nm, PLACEMENT_TIP_NM) + MARK_RADIUS_NM
    skirt = math.sqrt(max(reach**2 - (reach - top) ** 2, 0.0)) if top < reach else reach
    stretch = float(np.linalg.svd(s, compute_uv=False).max())
    radius_nm = (math.hypot(length, width) / 2.0 + skirt) * stretch + 2 * pixel
    radius = radius_nm / pixel

    heights = np.zeros((size_px, size_px))
    placed: list[PlacedTile] = []
    for _ in range(n_tiles):
        centre = None
        for _ in range(PLACEMENT_TRIES):
            candidate = (
                float(rng.uniform(radius, size_px - radius)),
                float(rng.uniform(radius, size_px - radius)),
            )
            if all(math.dist(candidate, p.centre_px) > 2 * radius for p in placed):
                centre = candidate
                break
        if centre is None:
            break
        angle = float(rng.uniform(*angles_deg))
        transform = str(transforms[int(rng.integers(len(transforms)))])
        shows = "none" if rng.random() < face_down_fraction else "marks"

        x_axis, y_axis = frame_axes(angle)
        tx, ty, _ = TRANSFORMS[transform]
        drawn = marks if shows == "marks" else marks[:0]
        if missing_fraction > 0 and len(drawn):
            drawn = drawn[rng.random(len(drawn)) >= missing_fraction]
        local = np.column_stack([tx * drawn[:, 0], ty * anisotropy * drawn[:, 1]])
        # (col, row) components in true nm, from the tile's centre.
        offsets = local[:, :1] * x_axis + local[:, 1:] * y_axis

        r0, r1 = max(0, int(centre[0] - radius)), min(size_px, int(centre[0] + radius) + 2)
        c0, c1 = max(0, int(centre[1] - radius)), min(size_px, int(centre[1] + radius) + 2)
        rows, cols = np.mgrid[r0:r1, c0:c1]
        reported = np.stack([cols.ravel() * pixel, rows.ravel() * pixel])
        centre_true = s_inv @ np.array([centre[1] * pixel, centre[0] * pixel])
        d = (s_inv @ reported).T - centre_true  # true nm from the tile's centre, (x, y)

        z = _sheet_profile(
            d @ x_axis,
            d @ y_axis,
            half_length=length / 2.0,
            half_width=width / 2.0,
            height_nm=height_nm,
            tip_radius_nm=tip_radius_nm,
        )
        if len(offsets):
            r2 = ((d[:, None, :] - offsets[None, :, :]) ** 2).sum(axis=2)
            apex = top - bump + np.sqrt(np.maximum(bump**2 - r2, 0.0))
            apex = np.where(r2 <= bump**2, apex, 0.0).max(axis=1)
            z = np.maximum(z, apex)
        window = heights[r0:r1, c0:c1]
        heights[r0:r1, c0:c1] = np.maximum(window, z.reshape(window.shape))
        placed.append(
            PlacedTile(centre_px=centre, angle_deg=angle, transform=transform, shows=shows)
        )

    heights = _instrument(
        heights,
        rng,
        drift_shear=0.0,
        tilt_nm=tilt_nm,
        bow_nm=0.0,
        line_noise_nm=line_noise_nm,
        streak_lines=0,
        streak_height_nm=height_nm,
        noise_nm=noise_nm,
    )
    return CalibrationScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel, source="synthetic-calibration"),
        truth=tuple(placed),
        scanner=ScannerTruth(
            scale_x=scale_x,
            scale_y=scale_y,
            skew_deg=skew_deg,
            anisotropy=anisotropy,
            tip_radius_nm=tip_radius_nm,
        ),
    )

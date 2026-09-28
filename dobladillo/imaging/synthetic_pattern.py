"""Synthetic scans of patterned sheets, with the answer written down.

The sibling of `synthetic`, for E8. Each sheet is placed at a known angle,
the right way round or mirrored, marked or not, with marks knocked out at
random, and the scan carries the same defects as `synthetic_scan`: tilt,
per-line offsets and pixel noise. What the detector in `imaging.pattern` must
recover is in `truth`.

**How a mark is drawn.** A hairpin is a small object on a flat sheet, and what
the AFM records is the tip riding over it. A sphere of radius R passing over
a bump of radius a and height h has its apex at

    z(r) = h - (R + a) + sqrt((R + a)^2 - r^2)

for r measured from the bump's axis, down to the sheet at
r = sqrt(2 (R + a) h - h^2). It is `synthetic._stamp_rectangle`'s edge profile
turned round an axis. a = 1 nm is the radius of a DNA duplex in scadnano's
geometry; the height h is a parameter, because nothing here predicts it. The
marks are combined by taking the highest at each pixel -- the tip touches the
tallest thing under it -- and then added to the sheet.

**Placing a mark the other way round.** The designed marks are in nm on the
sheet, seen from the marked face. A particle rotated by a half turn has them
at (-x, -y); one mirrored about its long axis at (x, -y); about its short
axis at (-x, y). This is done on the nm coordinates directly, not through the
cell indices the detector uses, so the renderer and the reader do not share
the transform they are testing. They do share `imaging.pattern.frame_axes`,
the definition of which way is up in an image; the tests pin that one on its
own, with a mark placed by hand.

This is a test instrument, not a simulator. It makes no claim about what a
hairpin on a real sheet looks like, how tall it stands in your buffer, or what
fraction of sheets land marks-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.pattern import TRANSFORMS, PatternGrid, frame_axes
from dobladillo.imaging.synthetic import SHEET_HEIGHT_NM, _stamp_rectangle

#: Radius of the thing under the tip, nm: one duplex, 2 nm across, as
#: scadnano's geometry has it (helix_radius = 1.0).
MARK_RADIUS_NM: Final = 1.0

#: How a placed sheet shows its marks.
SHOWS: Final = ("marks", "none")


@dataclass(frozen=True)
class PlacedSheet:
    """One sheet as rendered: where, which way round, and what it shows."""

    centre_px: tuple[float, float]
    angle_deg: float
    transform: str
    shows: str  # "marks" | "none"
    marks_drawn: int
    marks_designed: int

    @property
    def expected(self) -> str:
        """The verdict a correct reader gives this sheet, all marks present."""
        if self.shows == "none":
            return "blank"
        return "mirrored" if TRANSFORMS[self.transform][2] else "pattern"

    def as_dict(self) -> dict[str, Any]:
        return {
            "centre_px": [round(v, 1) for v in self.centre_px],
            "angle_deg": round(self.angle_deg, 1),
            "transform": self.transform,
            "shows": self.shows,
            "marks_drawn": self.marks_drawn,
            "marks_designed": self.marks_designed,
            "expected": self.expected,
        }


@dataclass(frozen=True)
class PatternScan:
    image: HeightMap
    truth: tuple[PlacedSheet, ...]


def _stamp_marks(
    heights: np.ndarray,
    *,
    centre: tuple[float, float],
    angle_deg: float,
    marks_nm: list[tuple[float, float]],
    height_nm: float,
    pixel_nm: float,
    tip_radius_nm: float,
) -> None:
    """Draw marks, given in nm in the sheet's own frame, onto the image."""
    if not marks_nm:
        return
    x_axis, y_axis = frame_axes(angle_deg)
    rows, cols = heights.shape
    radius = tip_radius_nm + MARK_RADIUS_NM
    reach_nm = float(np.sqrt(max(2 * radius * height_nm - height_nm**2, 0.0)))
    reach = int(np.ceil(reach_nm / pixel_nm)) + 1
    layer = np.zeros_like(heights)
    for x, y in marks_nm:
        col = centre[1] + (x * x_axis[0] + y * y_axis[0]) / pixel_nm
        row = centre[0] + (x * x_axis[1] + y * y_axis[1]) / pixel_nm
        r0, r1 = max(0, int(row) - reach), min(rows, int(row) + reach + 2)
        c0, c1 = max(0, int(col) - reach), min(cols, int(col) + reach + 2)
        if r0 >= r1 or c0 >= c1:
            continue
        yy, xx = np.mgrid[r0:r1, c0:c1]
        distance = np.hypot((yy - row) * pixel_nm, (xx - col) * pixel_nm)
        z = height_nm - radius + np.sqrt(np.maximum(radius**2 - distance**2, 0.0))
        z = np.where(distance <= reach_nm, np.clip(z, 0.0, height_nm), 0.0)
        layer[r0:r1, c0:c1] = np.maximum(layer[r0:r1, c0:c1], z)
    heights += layer


def patterned_scan(
    grid: PatternGrid,
    *,
    sheet_nm: tuple[float, float],
    placements: list[tuple[str, str]],
    size_px: int = 512,
    scan_nm: float = 1000.0,
    height_nm: float = SHEET_HEIGHT_NM,
    mark_height_nm: float = 2.0,
    missing_fraction: float = 0.0,
    tip_radius_nm: float = 10.0,
    noise_nm: float = 0.12,
    tilt_nm: float = 6.0,
    line_noise_nm: float = 0.25,
    bow_nm: float = 0.0,
    drift_shear: float = 0.0,
    streak_lines: int = 0,
    seed: int = 0,
) -> PatternScan:
    """One scan of sheets, each `(transform, shows)` from `placements`.

    `transform` is a key of `imaging.pattern.TRANSFORMS`; `shows` is "marks"
    or "none" (face-down, or an unmarked sheet). `missing_fraction` knocks out
    that fraction of marks at random on every marked sheet: a staple that did
    not fold in, or a hairpin the tip swept away. Sheets that do not fit are
    dropped, and `truth` has only the ones drawn.

    `bow_nm`, `drift_shear` and `streak_lines` are `synthetic_scan`'s
    artefacts, applied the same way: a parabolic scanner bow, a slow-axis
    shear from thermal drift, and a band of lines where the tip dragged
    something. The shear matters more here than for a footprint: it moves a
    mark relative to the cell it was put in.
    """
    for transform, shows in placements:
        if transform not in TRANSFORMS or shows not in SHOWS:
            raise ValueError(f"unknown placement {(transform, shows)}")
    rng = np.random.default_rng(seed)
    pixel_nm = scan_nm / size_px
    heights = np.zeros((size_px, size_px))
    length_px, width_px = sheet_nm[0] / pixel_nm, sheet_nm[1] / pixel_nm
    # Whatever the angle, a sheet and its tip-drawn skirt fit in a circle of
    # half its diagonal plus the skirt. Keeping those circles apart and inside
    # the frame means no two sheets merge and none touches the edge, so the
    # truth never claims a sheet the reader correctly excluded.
    skirt = float(np.sqrt(2 * tip_radius_nm * max(height_nm, mark_height_nm))) / pixel_nm
    radius = float(np.hypot(length_px, width_px)) / 2 + skirt + 2
    placed: list[PlacedSheet] = []

    for transform, shows in placements:
        centre = None
        for _ in range(300):
            candidate = (
                float(rng.uniform(radius, size_px - radius)),
                float(rng.uniform(radius, size_px - radius)),
            )
            if all(
                np.hypot(candidate[0] - p.centre_px[0], candidate[1] - p.centre_px[1]) > 2 * radius
                for p in placed
            ):
                centre = candidate
                break
        if centre is None:
            continue
        angle = float(rng.uniform(0, 180))
        _stamp_rectangle(
            heights,
            centre=centre,
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
        )
        sx, sy, _ = TRANSFORMS[transform]
        marks = [(sx * x, sy * y) for x, y in grid.marks_nm]
        if shows == "none":
            marks = []
        elif missing_fraction > 0:
            keep = rng.random(len(marks)) >= missing_fraction
            marks = [m for m, k in zip(marks, keep, strict=True) if k]
        _stamp_marks(
            heights,
            centre=centre,
            angle_deg=angle,
            marks_nm=marks,
            height_nm=mark_height_nm,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
        )
        placed.append(
            PlacedSheet(
                centre_px=centre,
                angle_deg=angle,
                transform=transform,
                shows=shows,
                marks_drawn=len(marks),
                marks_designed=len(grid.marks_nm),
            )
        )

    yy, xx = np.mgrid[0:size_px, 0:size_px]
    if drift_shear:
        shift = (drift_shear * yy).astype(int)
        heights = heights[np.arange(size_px)[:, None], np.clip(xx + shift, 0, size_px - 1)]
    heights = heights + tilt_nm * (xx / size_px) + 0.6 * tilt_nm * (yy / size_px)
    if bow_nm:
        u, v = 2 * xx / size_px - 1, 2 * yy / size_px - 1
        heights = heights + bow_nm * (u**2 + 0.7 * v**2)
    heights = heights + rng.normal(0, line_noise_nm, (size_px, 1))
    if streak_lines:
        first = int(rng.integers(0, max(1, size_px - streak_lines)))
        band = slice(first, first + streak_lines)
        heights[band, :] = heights[band, :] + height_nm * rng.uniform(0.6, 1.4)
    heights = heights + rng.normal(0, noise_nm, heights.shape)
    return PatternScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source="synthetic-pattern"),
        truth=tuple(placed),
    )

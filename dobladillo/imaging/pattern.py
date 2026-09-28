"""Reading a pattern of raised marks off a flat particle, orientation included.

Nothing here knows about DNA, like the rest of `imaging`. A pattern is a grid
of rectangular cells laid over a flat particle, some of them "on" (carrying
something taller than the sheet); `parts.pattern` builds one from a design and
`experiments.pattern` feeds it scans. This module answers one question per
particle: which cells stand proud, and which of four ways round is that the
designed pattern?

**Four ways round, not eight.** A rectangle's long axis is found from its
outline, so what is unknown is only the symmetry group of a rectangle: the
identity, a half turn, and two mirror images. A particle that landed the
other face up is seen mirrored -- through the sheet, if its marks are visible
at all -- and which of the two mirrors applies is just a half turn apart. So
the verdicts are `pattern` (identity or half turn), `mirrored` (either mirror),
`blank` (no cell stands proud) and `not_found` (something stands proud, but it
is not the pattern any way round).

**The coordinate convention, which the verdict depends on.** The grid is drawn
as seen FROM THE MARKED FACE: x to the right, y up. An image is taken to be a
view from the tip's side with row 0 at the top and columns to the right, as
Gwyddion and every instrument's viewer display it. So a particle that lies
marks-up and is read the right way round comes out `pattern`, and if every
particle in a real session reads `mirrored` the likeliest author is a reader
that stores its rows bottom-up, not the chemistry. The gate should count both
and report the split: the split is a check on the convention as much as on
the sample.

**Unique reading, by construction.** The four transforms of the pattern are
compared as codewords: `min_distance` is the smallest Hamming distance between
the pattern and any of its three other images. A reading within
`(min_distance - 1) // 2` cells of one of them is within that radius of no
other, so a verdict can never be a coin toss between `pattern` and `mirrored`.
A pattern that is symmetric under any of the three has distance zero and is
refused where it is designed (`parts.pattern`).

**What a cell's value is.** The median height over the inner part of the cell
(`INNER_FRACTION` of each side), minus the particle's sheet level, the median
over all cells. A cell is "on" when that excess is above BOTH `SPOT_SIGMA`
times the image's background noise and half the typical excess of the
tallest cells (see `read_cells`). The inner part only, because a tip draws
every mark wider than it is: a 10 nm tip draws a 2 nm mark about
sqrt(2 R h) = 6 nm in radius, which reaches into the next cell's edge but not
its middle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.imaging.classify import Fraction
from dobladillo.imaging.particles import DETECT_SIGMA

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from dobladillo.imaging.heightmap import HeightMap
    from dobladillo.imaging.particles import Particle

Cell = tuple[int, int]  # (column, row); row 0 at the bottom, seen from the marked face

#: A mark must stand this far above the sheet, in multiples of the background
#: noise, to count. The same multiple a particle needs to stand above the mica
#: (`particles.DETECT_SIGMA`): a cell's value is a median over many pixels, so
#: this is conservative, and it is conservative on purpose -- a real sheet has
#: texture that a synthetic one does not, and the negative control (unmarked
#: rectangles from the same session) is what shows whether it is conservative
#: enough.
SPOT_SIGMA: Final = DETECT_SIGMA

#: The part of each cell that is sampled, per side. See the module docstring.
INNER_FRACTION: Final = 0.6

#: A cell must span at least this many pixels on its short side to be read.
#: Below it the inner part of a cell is a pixel or two, and a verdict would
#: rest on single-pixel noise. A 2 x 2 um overview at 512 pixels is 3.9 nm per
#: pixel against ~10 nm cells: not readable, and the command says so.
MIN_PIXELS_PER_CELL: Final = 4.0

#: name: (sign on x, sign on y, is a mirror image)
TRANSFORMS: Final[dict[str, tuple[int, int, bool]]] = {
    "identity": (1, 1, False),
    "rotated_180": (-1, -1, False),
    "mirrored_x": (-1, 1, True),
    "mirrored_y": (1, -1, True),
}

VERDICTS: Final = ("pattern", "mirrored", "not_found", "blank")


@dataclass(frozen=True)
class GridCell:
    """One cell: where it is on the sheet, nm from the sheet's centre, and whether it is on."""

    col: int
    row: int
    x_nm: tuple[float, float]
    y_nm: tuple[float, float]
    on: bool

    @property
    def centre_nm(self) -> tuple[float, float]:
        return (sum(self.x_nm) / 2.0, sum(self.y_nm) / 2.0)

    @property
    def size_nm(self) -> tuple[float, float]:
        return (self.x_nm[1] - self.x_nm[0], self.y_nm[1] - self.y_nm[0])


@dataclass(frozen=True)
class PatternGrid:
    """A designed pattern, in nanometres on the particle, seen from the marked face.

    `marks_nm` are where the individual marks sit (for rendering synthetic
    scans); the detector reads cells, not marks.
    """

    columns: int
    rows: int
    cells: tuple[GridCell, ...]
    marks_nm: tuple[tuple[float, float], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        seen = {(c.col, c.row) for c in self.cells}
        wanted = {(c, r) for c in range(self.columns) for r in range(self.rows)}
        if seen != wanted or len(self.cells) != len(wanted):
            raise ValueError("a pattern grid needs exactly one cell per (column, row)")

    @property
    def on(self) -> frozenset[Cell]:
        return frozenset((c.col, c.row) for c in self.cells if c.on)

    def transform(self, cells: Iterable[Cell], name: str) -> frozenset[Cell]:
        """Where `cells` land under one of the four transforms, in grid indices."""
        sx, sy, _ = TRANSFORMS[name]
        return frozenset(
            (c if sx > 0 else self.columns - 1 - c, r if sy > 0 else self.rows - 1 - r)
            for c, r in cells
        )

    def distances(self) -> dict[str, int]:
        """Hamming distance from the pattern to each of its images."""
        on = self.on
        return {name: len(on ^ self.transform(on, name)) for name in TRANSFORMS}

    @property
    def min_distance(self) -> int:
        return min(d for name, d in self.distances().items() if name != "identity")

    @property
    def decoding_radius(self) -> int:
        """Cells that may be wrong while the reading stays unique."""
        return max(0, (self.min_distance - 1) // 2)

    @property
    def min_cell_nm(self) -> float:
        return min(min(c.size_nm) for c in self.cells)

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "view": "seen from the marked face: x to the right, y up; nm from the sheet centre",
            "cells": [
                {
                    "col": c.col,
                    "row": c.row,
                    "x_nm": [round(v, 3) for v in c.x_nm],
                    "y_nm": [round(v, 3) for v in c.y_nm],
                    "on": c.on,
                }
                for c in self.cells
            ],
            "marks_nm": [[round(x, 3), round(y, 3)] for x, y in self.marks_nm],
            "min_distance": self.min_distance,
            "decoding_radius": self.decoding_radius,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternGrid:
        cells = tuple(
            GridCell(
                col=int(c["col"]),
                row=int(c["row"]),
                x_nm=(float(c["x_nm"][0]), float(c["x_nm"][1])),
                y_nm=(float(c["y_nm"][0]), float(c["y_nm"][1])),
                on=bool(c["on"]),
            )
            for c in data["cells"]
        )
        return cls(
            columns=int(data["columns"]),
            rows=int(data["rows"]),
            cells=tuple(sorted(cells, key=lambda c: (c.col, c.row))),
            marks_nm=tuple((float(x), float(y)) for x, y in data.get("marks_nm", [])),
        )

    def render(self, cells: Iterable[Cell] | None = None) -> str:
        """The cells as text, top row first, as seen from the marked face."""
        chosen = self.on if cells is None else frozenset(cells)
        return "\n".join(
            "".join("X" if (c, r) in chosen else "." for c in range(self.columns))
            for r in reversed(range(self.rows))
        )


def frame_axes(angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """The design's x and y axes in image (col, row) coordinates, for a
    particle whose long axis is at `angle_deg` and which is seen the right way
    round (identity transform).

    `angle_deg` is `Particle.angle_deg`: measured from +col towards +row, the
    convention `synthetic._stamp_rectangle` renders with. y is x turned a
    quarter anticlockwise AS DISPLAYED, with row 0 at the top: (dc, dr) goes
    to (dr, -dc). At 0 degrees x is to the right and y is up the screen.
    """
    theta = math.radians(angle_deg)
    x = np.array([math.cos(theta), math.sin(theta)])
    y = np.array([x[1], -x[0]])
    return x, y


def background_noise_nm(image: HeightMap, background: np.ndarray) -> float:
    """Pixel noise of the levelled background: the scale a mark is judged on."""
    return float(image.heights_nm[background].std())


@dataclass(frozen=True)
class Reading:
    """What one particle showed."""

    verdict: str
    transform: str | None
    distance: int
    hits: int
    marks: int
    spurious: int
    observed: frozenset[Cell]
    excess_nm: dict[Cell, float]
    sheet_nm: float
    threshold_nm: float
    orientation_deg: float | None

    @property
    def found(self) -> bool:
        return self.verdict in ("pattern", "mirrored")

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "transform": self.transform,
            "distance": self.distance,
            "hits": self.hits,
            "of": self.marks,
            "spurious": self.spurious,
            "observed": sorted([list(c) for c in self.observed]),
            "sheet_nm": round(self.sheet_nm, 3),
            "threshold_nm": round(self.threshold_nm, 3),
            "orientation_deg": None
            if self.orientation_deg is None
            else round(self.orientation_deg, 1),
            "max_excess_nm": round(max(self.excess_nm.values()), 3) if self.excess_nm else None,
        }


def sample_cells(
    image: HeightMap,
    *,
    centre_px: tuple[float, float],
    angle_deg: float,
    grid: PatternGrid,
    inner: float = INNER_FRACTION,
) -> dict[Cell, float]:
    """The median height of each cell's inner part, in the identity frame.

    Bilinear interpolation, at about one sample per pixel along each side
    and at least three.
    """
    from scipy import ndimage

    x_axis, y_axis = frame_axes(angle_deg)
    row0, col0 = centre_px
    pixel = image.pixel_nm
    values: dict[Cell, float] = {}
    for cell in grid.cells:
        (x0, x1), (y0, y1) = cell.x_nm, cell.y_nm
        cx, cy = cell.centre_nm
        hx, hy = inner * (x1 - x0) / 2.0, inner * (y1 - y0) / 2.0
        nx = max(3, math.ceil(2 * hx / pixel) + 1)
        ny = max(3, math.ceil(2 * hy / pixel) + 1)
        xs, ys = np.meshgrid(np.linspace(cx - hx, cx + hx, nx), np.linspace(cy - hy, cy + hy, ny))
        cols = col0 + (xs * x_axis[0] + ys * y_axis[0]) / pixel
        rows = row0 + (xs * x_axis[1] + ys * y_axis[1]) / pixel
        samples = ndimage.map_coordinates(
            image.heights_nm, [rows.ravel(), cols.ravel()], order=1, mode="nearest"
        )
        values[(cell.col, cell.row)] = float(np.median(samples))
    return values


def read_cells(
    values: dict[Cell, float],
    grid: PatternGrid,
    *,
    noise_nm: float,
    spot_sigma: float = SPOT_SIGMA,
    orientation_deg: float = 0.0,
) -> Reading:
    """Decide which cells are on, and which transform of the pattern that is."""
    sheet = float(np.median(list(values.values())))
    excess = {cell: value - sheet for cell, value in values.items()}
    on = grid.on
    # Half the height of the marks, once they clear the noise: the same
    # half-height convention as a particle's outline, and for the same
    # reason. A tip draws a tall mark wide enough that its skirt reaches into
    # the middle of the next cell; measured on synthetic scans, 4 nm marks
    # under a 10 nm tip lit up empty neighbours above a noise-only threshold
    # and two thirds of the sheets were misread. "The marks" are the tallest
    # len(on) cells, whichever they are, so this uses how many marks were
    # designed and nothing about where.
    tallest = sorted(excess.values(), reverse=True)[: max(1, len(on))]
    threshold = max(spot_sigma * noise_nm, float(np.median(tallest)) / 2.0)
    observed = frozenset(cell for cell, e in excess.items() if e > threshold)

    distances = {name: len(observed ^ grid.transform(on, name)) for name in TRANSFORMS}
    # Ties broken by the order of TRANSFORMS, which only matters beyond the
    # decoding radius, where the verdict is `not_found` anyway.
    best = min(TRANSFORMS, key=lambda name: distances[name])
    expected = grid.transform(on, best)
    hits = len(observed & expected)
    spurious = len(observed - expected)

    if not observed:
        verdict, transform = "blank", None
    elif distances[best] <= grid.decoding_radius:
        verdict = "mirrored" if TRANSFORMS[best][2] else "pattern"
        transform = best
    else:
        verdict, transform = "not_found", None

    orientation = None
    if transform is not None:
        # The design's +x in the image: along the long axis for the identity
        # and the y-mirror, against it for the half turn and the x-mirror.
        flip = TRANSFORMS[transform][0] < 0
        orientation = (orientation_deg + (180.0 if flip else 0.0)) % 360.0
    return Reading(
        verdict=verdict,
        transform=transform,
        distance=distances[best],
        hits=hits,
        marks=len(on),
        spurious=spurious,
        observed=observed,
        excess_nm=excess,
        sheet_nm=sheet,
        threshold_nm=threshold,
        orientation_deg=orientation,
    )


def read_particle(
    image: HeightMap,
    particle: Particle,
    grid: PatternGrid,
    *,
    noise_nm: float,
    spot_sigma: float = SPOT_SIGMA,
) -> Reading:
    """Sample the grid over one particle and read it."""
    values = sample_cells(
        image, centre_px=particle.centre_px, angle_deg=particle.angle_deg, grid=grid
    )
    return read_cells(
        values,
        grid,
        noise_nm=noise_nm,
        spot_sigma=spot_sigma,
        orientation_deg=particle.angle_deg,
    )


def readable(image: HeightMap, grid: PatternGrid) -> bool:
    """Is the pixel fine enough for this grid's cells to be read at all?"""
    return grid.min_cell_nm / image.pixel_nm >= MIN_PIXELS_PER_CELL


@dataclass(frozen=True)
class PatternSummary:
    """A population of readings, as fractions with the intervals they support."""

    counts: dict[str, int]
    total: int

    @property
    def found(self) -> Fraction:
        """Pattern either way round, among every particle read."""
        return Fraction(self.counts["pattern"] + self.counts["mirrored"], self.total)

    @property
    def found_among_marked(self) -> Fraction:
        """Pattern either way round, among particles where anything stood proud.

        The fraction that says whether the marks, where visible, spell the
        design. A face-down particle hides its marks (Rothemund 2006, Supp.
        Note S6: flipped structures "image poorly"), so it lands in `blank`
        and is left out of this denominator rather than counted as a miss.
        """
        marked = self.total - self.counts["blank"]
        return Fraction(self.counts["pattern"] + self.counts["mirrored"], marked)

    @property
    def mirrored_share(self) -> Fraction:
        """Of the particles where the pattern was found, how many read mirrored."""
        return Fraction(self.counts["mirrored"], self.counts["pattern"] + self.counts["mirrored"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "read": self.total,
            "verdicts": self.counts,
            "found": self.found.as_dict(),
            "found_among_marked": self.found_among_marked.as_dict(),
            "mirrored_share_of_found": self.mirrored_share.as_dict(),
        }


def summarise(readings: Sequence[Reading]) -> PatternSummary:
    counts = {verdict: 0 for verdict in VERDICTS}
    for reading in readings:
        counts[reading.verdict] += 1
    return PatternSummary(counts=counts, total=len(readings))

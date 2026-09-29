"""A lateral-calibration tile: E8's rectangle carrying a sparse ruler of marks.

**What it is.** E8's patterned rectangle (`parts.pattern`) with a different
pattern and nothing else changed: the same E1 sheet, the same hairpin on the
same staple ends, the same marked face, the same pooling rule. Every mark is
a cell of four hairpins exactly as in E8. Only the picture differs, because
the job differs. E8 asks "is the pattern there?"; a calibration asks "how far
apart are these marks in the image, compared with the design?". So the marks
are chosen to be a ruler:

- **Isolated.** No two marked cells touch, not even diagonally, so every
  cell images as a blob of its own and its centroid is not pulled by a
  neighbour's skirt. Diagonal counts because a tip draws a mark round: a
  10 nm tip draws a 2 nm mark about 6 nm in radius, and diagonal neighbours
  are 14 nm apart centre to centre.
- **Spread.** All four corner cells are marked and the rest fill both axes,
  so the cell centres span as much of the sheet as the margins allow: about
  73 nm along the helices and 39 nm across them. A scale is a ratio of
  distances, and its error falls with the distances.
- **Chiral.** A particle lands at any angle, either way up; the four images
  of the pattern under the rectangle's symmetries must differ, or a
  mismatched landing would be fitted as a distorted scanner.
  `patterned_rectangle` refuses a pattern whose images differ in fewer than
  three cells; this one differs in eight from each (decoding radius 3), found
  by exhaustive search over every isolated pattern on the usable 8 x 5 cells
  that includes all four corners: none has more marks (12) with a larger
  distance.

**Why centroids, and why that makes this better than the outline.** A
symmetric tip broadens every feature by the same amount on every side, so it
moves an edge outward and leaves a centroid where it was. A scale read from
outlines therefore depends on the tip radius (the dominant systematic in any
width here, see `compare.corrections`); one read from the distances between
mark centroids does not. The tests show it: the same particles imaged with
5 and 15 nm tips give the same centroids to a fraction of a nanometre.

**The designed positions, and how well they are known.** In the object
frame, nm from the sheet's centre, x along the helices (offset increasing)
and y across them (helix index increasing), seen from the marked face -- the
frame `imaging.pattern` reads in. A feature is the centroid of its cell's
hairpin staple ends, which for this lattice is the cell's centre.

- x is a count of base pairs times the rise. The count is exact (the twist
  deletions are counted out, as `parts.pattern` does); the rise is
  `constants.RISE_PER_BP_NM`, 0.34 nm, the design document's figure. Two
  rises are in circulation, and the other one, scadnano's 0.332, is 2.4%
  below it (`constants.RISE_PER_BP_RANGE_NM`). Nothing here says which is
  nearer a dried tile, so the whole gap is taken as the half-width of a
  rectangular distribution about 0.34: 1.36% standard uncertainty. Not the
  gap's midpoint with half of it: that would claim the truth lies between
  two values of which one is the nominal, which nobody has measured.
- y is a count of helices times the inter-helix spacing, and the spacing is
  the weak link: `constants.INTERHELIX_SPACING_NM` is a RANGE (2.25-2.6 nm),
  set by electrostatics and so by Mg2+ and by how the sheet dried. Taken as
  the middle with the range rectangular: 4.2%. That is too loose to be a
  ruler, so `calibration.lateral` does not use it as one; it FITS the
  across-helix scale as an object anisotropy and uses the rise, the robust
  number, as the reference. The 4.2% is stated so that nobody mistakes the
  nominal y positions for known ones.

scadnano draws this lattice at 3.0 nm between helix axes
(`_scadnano.interhelix_spacing_nm`), outside the constants' range; that is a
drawing convention, and `parts.pattern`'s grid (which uses it) is for
reading which cells are on, not for measuring. Flagged here rather than
resolved: the fitted anisotropy of a real session is a measurement of that
spacing, as prepared.

This file does not claim that a tile folded and dried in any given lab has
these dimensions. Origami dimensions move by several percent with buffer,
Mg2+, deposition and drying. The reference built from it is `nominal`, not
`certified`, and a calibration made with it is not traceable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from dobladillo import _scadnano as ad
from dobladillo.constants import (
    INTERHELIX_SPACING_NM,
    RISE_PER_BP_NM,
    RISE_PER_BP_RANGE_NM,
)
from dobladillo.parts.pattern import (
    CELL_BP,
    CELL_HELICES,
    MARGIN_HELICES,
    PatternedRectangle,
    _x_nm,
    patterned_rectangle,
)

if TYPE_CHECKING:
    import scadnano as sc

__all__ = [
    "CALIBRATION_PATTERN",
    "CalibrationTile",
    "TileFeature",
    "calibration_tile",
    "isolated",
]

#: The ruler, top row first, seen from the marked face with the helices
#: running left to right (the convention of `parts.pattern.DEFAULT_PATTERN`).
#: Rows 0, 2 and 4 only, so marks in one column are two cells apart; columns
#: 0 and 9 hold edge staples and are never marked. See the module docstring.
CALIBRATION_PATTERN: Final = (
    ".X.X.X..X.",
    "..........",
    "..X.X.X.X.",
    "..........",
    ".X..X.X.X.",
)


def _rect_uncertainty(bounds: tuple[float, float]) -> tuple[float, float]:
    """Middle of a range, and its standard uncertainty as a relative number,
    treating the range as a rectangular distribution (GUM 4.3.7): the
    half-width over sqrt(3). The honest reading of "somewhere in this range"."""
    low, high = bounds
    middle = (low + high) / 2.0
    return middle, (high - low) / 2.0 / math.sqrt(3.0) / middle


#: Nominal rise and inter-helix spacing, nm, with their relative standard
#: uncertainties. Derived from the constants, not chosen: the rise is
#: RISE_PER_BP_NM with the gap to the other value in circulation as the
#: half-width (see the module docstring), the spacing the middle of its range.
RISE_NM: Final = RISE_PER_BP_NM
RISE_RELATIVE_UNCERTAINTY: Final = (
    (RISE_PER_BP_RANGE_NM[1] - RISE_PER_BP_RANGE_NM[0]) / math.sqrt(3.0) / RISE_NM
)
SPACING_NM, SPACING_RELATIVE_UNCERTAINTY = _rect_uncertainty(INTERHELIX_SPACING_NM)


def isolated(pattern: tuple[str, ...]) -> bool:
    """No two marked cells touch, edges or corners."""
    on = {(c, r) for r, line in enumerate(pattern) for c, ch in enumerate(line) if ch == "X"}
    return not any(
        (c + dc, r + dr) in on
        for c, r in on
        for dc in (-1, 0, 1)
        for dr in (-1, 0, 1)
        if (dc, dr) != (0, 0)
    )


@dataclass(frozen=True)
class TileFeature:
    """One marked cell: its designed centre and the hairpins that draw it.

    Positions are nm in the object frame at the NOMINAL rise and spacing
    (see the module docstring); `cell_centre_nm` is the centre of the cell's
    box, `x_nm`/`y_nm` the centroid of its hairpin staple ends, which is what
    an image shows. The two agree to well under a base here.
    """

    name: str
    cell: tuple[int, int]
    x_nm: float
    y_nm: float
    cell_centre_nm: tuple[float, float]
    marks_nm: tuple[tuple[float, float], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cell": list(self.cell),
            "x_nm": round(self.x_nm, 4),
            "y_nm": round(self.y_nm, 4),
            "cell_centre_nm": [round(v, 4) for v in self.cell_centre_nm],
            "marks_nm": [[round(x, 4), round(y, 4)] for x, y in self.marks_nm],
        }


@dataclass(frozen=True)
class CalibrationTile:
    """E8's rectangle with the calibration pattern, and its designed ruler."""

    patterned: PatternedRectangle
    features: tuple[TileFeature, ...]
    sheet_nm: tuple[float, float]
    rise_nm: float
    spacing_nm: float
    rise_relative_uncertainty: float
    spacing_relative_uncertainty: float

    @property
    def design(self) -> sc.Design:
        return self.patterned.design

    @property
    def pattern(self) -> tuple[str, ...]:
        return self.patterned.pattern

    @property
    def scaffold(self) -> ad.ScaffoldAccounting:
        return self.patterned.scaffold

    @property
    def staple_count(self) -> int:
        return self.patterned.staple_count

    @property
    def marker_count(self) -> int:
        return len(self.patterned.markers)

    @property
    def dimensions_nm(self) -> tuple[float, float]:
        return self.patterned.dimensions_nm

    @property
    def base_part(self) -> str:
        return self.patterned.base_part

    @property
    def marks_nm(self) -> tuple[tuple[float, float], ...]:
        """Every hairpin's staple end, nm, at the nominal geometry: what a
        synthetic scan draws."""
        return tuple(m for f in self.features for m in f.marks_nm)

    def order_design(self) -> sc.Design:
        return self.patterned.order_design()

    def span_nm(self) -> tuple[float, float]:
        """How far the feature centres reach along each axis."""
        xs = [f.x_nm for f in self.features]
        ys = [f.y_nm for f in self.features]
        return (max(xs) - min(xs), max(ys) - min(ys))

    def as_dict(self) -> dict[str, Any]:
        span = self.span_nm()
        return {
            **self.patterned.as_dict(),
            "part": "calibration_tile",
            "ruler": {
                "frame": "object frame, nm from the sheet centre, seen from the marked face: "
                "x along the helices (offset increasing), y across them (helix index increasing)",
                "rise_nm": round(self.rise_nm, 4),
                "rise_relative_uncertainty": round(self.rise_relative_uncertainty, 5),
                "spacing_nm": round(self.spacing_nm, 4),
                "spacing_relative_uncertainty": round(self.spacing_relative_uncertainty, 5),
                "sheet_nm": [round(v, 3) for v in self.sheet_nm],
                "span_nm": [round(v, 3) for v in span],
                "features": [f.as_dict() for f in self.features],
                "note": "nominal, not certified: see calibration.reference",
            },
        }


def calibration_tile(
    pattern: tuple[str, ...] = CALIBRATION_PATTERN, *, marker: str = "hairpin"
) -> CalibrationTile:
    """Build the tile and its ruler.

    Refuses a pattern whose marked cells touch (`isolated`), on top of
    everything `patterned_rectangle` refuses (ambiguous under the sheet's
    symmetries, too few staple ends facing the marked face, a hairpin that
    does not fold in time).

    `marker` is `hairpin` (all-DNA marks) or `biotin` (a 3' biotin on the same
    staple ends, for streptavidin-bound marks; K6). The ruler is the same.
    """
    pattern = tuple(pattern)
    if not isolated(pattern):
        raise ValueError(
            "a calibration pattern needs every marked cell isolated, edges and corners: "
            "two touching cells image as one blob, and its centroid is neither's"
        )
    patterned = patterned_rectangle(pattern, marker=marker)
    rectangle = patterned.rectangle
    helices, length = rectangle.helices, rectangle.length
    deletions = sorted(
        {
            x
            for d in ad.scaffold_strand(rectangle.design).domains
            if getattr(d, "helix", None) == 0
            for x in d.deletions
        }
    )
    half_x = _x_nm(length, deletions, RISE_NM) / 2.0
    mid_helix = (helices - 1) / 2.0

    by_cell: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for mark in patterned.markers:
        x = _x_nm(mark.offset, deletions, RISE_NM) + RISE_NM / 2.0 - half_x
        y = (mark.helix - mid_helix) * SPACING_NM
        by_cell.setdefault(mark.cell, []).append((x, y))

    features = []
    for (col, row), marks in sorted(by_cell.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        bottom = MARGIN_HELICES + row * CELL_HELICES - 0.5 - mid_helix
        centre = (
            (
                _x_nm(col * CELL_BP, deletions, RISE_NM)
                + _x_nm((col + 1) * CELL_BP, deletions, RISE_NM)
            )
            / 2.0
            - half_x,
            (bottom + CELL_HELICES / 2.0) * SPACING_NM,
        )
        features.append(
            TileFeature(
                name=f"c{col}r{row}",
                cell=(col, row),
                x_nm=sum(m[0] for m in marks) / len(marks),
                y_nm=sum(m[1] for m in marks) / len(marks),
                cell_centre_nm=centre,
                marks_nm=tuple(marks),
            )
        )
    return CalibrationTile(
        patterned=patterned,
        features=tuple(features),
        sheet_nm=(2.0 * half_x, helices * SPACING_NM),
        rise_nm=RISE_NM,
        spacing_nm=SPACING_NM,
        rise_relative_uncertainty=RISE_RELATIVE_UNCERTAINTY,
        spacing_relative_uncertainty=SPACING_RELATIVE_UNCERTAINTY,
    )

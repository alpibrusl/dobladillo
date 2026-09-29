"""The geometry of a reference object, and how far it can be trusted.

A calibration is a comparison: distances in an image against distances that
are known. This module holds the "known" side, and its main job is to keep
the word honest. Three things travel with every reference:

- **named features with positions**, nm, in the object's own frame. For the
  lateral fit a feature is something with a well-defined CENTROID -- a mark,
  a pit, a bead -- because a symmetric tip moves an edge and leaves a
  centroid alone (`parts.calibration_tile`).
- **how well those positions are known**, as a relative standard uncertainty
  per axis (a SCALE uncertainty: every x is off by the same factor, every y
  by another) and optionally a per-feature one in nm (each feature off by
  its own amount, the same on every particle). Both are systematic: imaging
  more particles does not average them away, which is why the lateral fit
  adds them in quadrature to its statistical uncertainty rather than hoping
  they are small.
- **a status**. `nominal` means derived from a design or a datasheet's
  typical values, uncertified; `certified` means a calibration certificate
  stands behind the positions and names a `source`. Only a certified
  reference makes a calibration traceable, and `calibration.lateral` reports
  `traceable: false` for anything else, however small its error bars.

`free_axis` says whether the fit should treat one axis of the reference as
unknown and fit it (`"y"`: the across-helix spacing of a DNA-origami tile,
which depends on conditions) or trust both (`None`). With `"y"`, the y scale
uncertainty is not a systematic of the calibration; it is what the fitted
object anisotropy measures.

**Other references.** Anything whose datasheet gives feature positions can
be declared as JSON (`save`/`load`, schema `dobladillo.reference/1`). No
commercial sample's values are written into this code: a datasheet's typical
dimensions are the vendor's claim about their product, they change between
lots, and the person holding the box should type in what their certificate
says, with its status and source. A nominal value typed in as `certified`
is a false claim that this module cannot detect; it only makes the claim
explicit and puts it in every result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

import numpy as np

if TYPE_CHECKING:
    from dobladillo.parts.calibration_tile import CalibrationTile

__all__ = [
    "SCHEMA",
    "STATUSES",
    "Feature",
    "ReferenceGeometry",
    "from_tile",
    "load",
]

SCHEMA: Final = "dobladillo.reference/1"

Status = Literal["nominal", "certified"]
STATUSES: Final = ("nominal", "certified")

#: A lateral fit needs at least three non-collinear points per particle to
#: fix an affine map; fewer and scale, skew and rotation trade off exactly.
MIN_FEATURES: Final = 3


@dataclass(frozen=True)
class Feature:
    """One named point of the reference, nm in the object frame."""

    name: str
    x_nm: float
    y_nm: float

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "x_nm": self.x_nm, "y_nm": self.y_nm}


@dataclass(frozen=True)
class ReferenceGeometry:
    """What a reference object is declared to look like, and on whose word.

    `relative_uncertainty` is the (x, y) relative STANDARD uncertainty of the
    positions' scale; `feature_uncertainty_nm` is a standard uncertainty per
    coordinate of each feature's own position, uncorrelated between features.
    `outline_nm`, if given, is the object's footprint (for finding it in an
    image); it is not used as a ruler.
    """

    name: str
    features: tuple[Feature, ...]
    relative_uncertainty: tuple[float, float]
    status: Status
    provenance: str
    source: str | None = None
    feature_uncertainty_nm: float = 0.0
    free_axis: Literal["y"] | None = None
    outline_nm: tuple[float, float] | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status is one of {STATUSES}, got {self.status!r}")
        if self.status == "certified" and not (self.source and self.source.strip()):
            raise ValueError(
                "a certified reference names its source (the certificate or standard); "
                "without one it is nominal"
            )
        if len(self.features) < MIN_FEATURES:
            raise ValueError(
                f"a reference needs at least {MIN_FEATURES} features, got {len(self.features)}"
            )
        names = [f.name for f in self.features]
        if len(set(names)) != len(names):
            raise ValueError("feature names must be unique")
        if any(u < 0 for u in self.relative_uncertainty) or self.feature_uncertainty_nm < 0:
            raise ValueError("uncertainties cannot be negative")
        if len(self.relative_uncertainty) != 2:
            raise ValueError("relative_uncertainty is (x, y)")
        if self.free_axis not in (None, "y"):
            raise ValueError(f"free_axis is 'y' or None, got {self.free_axis!r}")
        centred = self.positions_nm - self.positions_nm.mean(axis=0)
        if np.linalg.matrix_rank(centred, tol=1e-6) < 2:
            raise ValueError("the features are collinear; they cannot fix a 2D scale")

    @property
    def positions_nm(self) -> np.ndarray:
        return np.array([[f.x_nm, f.y_nm] for f in self.features], dtype=float)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.features)

    @property
    def traceable(self) -> bool:
        return self.status == "certified"

    @property
    def min_spacing_nm(self) -> float:
        """Closest distance between two features: sets how far a detected
        mark may sit from its predicted place and still be matched."""
        p = self.positions_nm
        d = np.hypot(*(p[:, None, :] - p[None, :, :]).transpose(2, 0, 1))
        d[np.diag_indices_from(d)] = np.inf
        return float(d.min())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "units": "nm",
            "frame": "the object's own frame; x and y as the reference defines them",
            "status": self.status,
            "source": self.source,
            "provenance": self.provenance,
            "relative_uncertainty": {
                "x": self.relative_uncertainty[0],
                "y": self.relative_uncertainty[1],
                "meaning": "relative standard uncertainty (k=1) of each axis's scale",
            },
            "feature_uncertainty_nm": self.feature_uncertainty_nm,
            "free_axis": self.free_axis,
            "outline_nm": None if self.outline_nm is None else list(self.outline_nm),
            "features": [f.as_dict() for f in self.features],
            "notes": list(self.notes),
        }

    def save(self, path: Path | str) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.as_dict(), indent=2) + "\n")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceGeometry:
        if data.get("schema") != SCHEMA:
            raise ValueError(f"not a reference geometry: schema {data.get('schema')!r}")
        if data.get("units", "nm") != "nm":
            raise ValueError(f"positions must be in nm, got {data.get('units')!r}")
        rel = data["relative_uncertainty"]
        outline = data.get("outline_nm")
        return cls(
            name=str(data["name"]),
            features=tuple(
                Feature(str(f["name"]), float(f["x_nm"]), float(f["y_nm"]))
                for f in data["features"]
            ),
            relative_uncertainty=(float(rel["x"]), float(rel["y"])),
            status=data["status"],
            provenance=str(data.get("provenance", "")),
            source=data.get("source"),
            feature_uncertainty_nm=float(data.get("feature_uncertainty_nm", 0.0)),
            free_axis=data.get("free_axis"),
            outline_nm=None if outline is None else (float(outline[0]), float(outline[1])),
            notes=tuple(str(n) for n in data.get("notes", [])),
        )


def load(path: Path | str) -> ReferenceGeometry:
    """Read a reference declared as JSON (see `ReferenceGeometry.as_dict`)."""
    return ReferenceGeometry.from_dict(json.loads(Path(path).read_text()))


def from_tile(tile: CalibrationTile | None = None) -> ReferenceGeometry:
    """The calibration tile's ruler as a reference: nominal, y left free.

    Builds the tile if none is given (a few seconds: it runs primer3 on the
    hairpin). The x uncertainty is the rise's range, the y uncertainty the
    inter-helix spacing's; with `free_axis="y"` the fit measures the second
    rather than trusting it.
    """
    if tile is None:
        from dobladillo.parts.calibration_tile import calibration_tile

        tile = calibration_tile()
    return ReferenceGeometry(
        name="dobladillo calibration tile",
        features=tuple(Feature(f.name, f.x_nm, f.y_nm) for f in tile.features),
        relative_uncertainty=(tile.rise_relative_uncertainty, tile.spacing_relative_uncertainty),
        status="nominal",
        provenance=(
            f"design-derived: x = base pairs x {tile.rise_nm:.3f} nm rise "
            "(constants.RISE_PER_BP_NM; uncertainty rectangular, half-width the gap to "
            "scadnano's 0.332), y = helices x "
            f"{tile.spacing_nm:.3f} nm spacing (constants.INTERHELIX_SPACING_NM, rectangular); "
            "feature = centroid of a marked cell's hairpin staple ends; "
            "pattern " + " / ".join(tile.pattern)
        ),
        source=None,
        feature_uncertainty_nm=0.0,
        free_axis="y",
        outline_nm=tile.sheet_nm,
        notes=(
            "The positions are the DESIGN's. A folded, deposited and dried tile differs by "
            "an amount that depends on the preparation (buffer, Mg2+, deposition, drying); "
            "that difference is not in these uncertainties.",
            "feature_uncertainty_nm is 0: every marked cell has the same local staple "
            "geometry (the lattice repeats every 32 bp), so a hairpin lean common to all "
            "cells is a translation, which the fit absorbs.",
        ),
    )

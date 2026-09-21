"""Images whose contents we chose, for testing measurement code.

There are no real AFM images yet, and there will not be until somebody spends
an afternoon at a microscope. Waiting for them to write the analysis would mean
writing it against no feedback at all, and then debugging it on the one
irreplaceable dataset.

So: render rectangles of known size, at known angles, in known numbers, with
the defects a real scan has -- tilted background, line noise, scanner drift,
a few aggregates. If the pipeline cannot recover what was put in, it will not
recover what it was not told.

This is a test instrument, not a simulator. It makes no claim about what real
origami look like; it makes images with a known answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: A single-layer origami sheet stands about this tall, dried on mica.
SHEET_HEIGHT_NM = 2.0


@dataclass(frozen=True)
class PlacedParticle:
    """What was put into the image, so it can be compared with what came out."""

    centre_px: tuple[float, float]
    length_nm: float
    width_nm: float
    height_nm: float
    angle_deg: float
    kind: str  # "rectangle" | "aggregate"

    def as_dict(self) -> dict[str, Any]:
        return {
            "centre_px": [round(v, 1) for v in self.centre_px],
            "length_nm": round(self.length_nm, 1),
            "width_nm": round(self.width_nm, 1),
            "height_nm": round(self.height_nm, 2),
            "angle_deg": round(self.angle_deg, 1),
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SyntheticScan:
    image: HeightMap
    truth: tuple[PlacedParticle, ...] = field(default_factory=tuple)

    @property
    def rectangles(self) -> tuple[PlacedParticle, ...]:
        return tuple(p for p in self.truth if p.kind == "rectangle")


def _stamp_rectangle(
    heights: np.ndarray,
    *,
    centre: tuple[float, float],
    length_px: float,
    width_px: float,
    height_nm: float,
    angle_deg: float,
    edge_px: float,
) -> None:
    """Draw one rotated rectangle with softened edges.

    Softened because a real tip is not a point. The direction matters and is
    easy to get backwards: a finite-radius tip BROADENS a feature, so the ramp
    extends outward past the true edge rather than eating inward from it, and
    the half-height contour sits on the true edge. Modelling it the other way
    makes half-height measurement look 20% low on a 36 nm feature, and
    "fixing" the measurement to match would be compensating for something real
    images do not do.
    """
    rows, cols = heights.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    angle = np.deg2rad(angle_deg)
    dy, dx = yy - centre[0], xx - centre[1]
    along = dx * np.cos(angle) + dy * np.sin(angle)
    across = -dx * np.sin(angle) + dy * np.cos(angle)

    def ramp(distance: np.ndarray, half: float) -> np.ndarray:
        # Full height inside half - edge/2, zero beyond half + edge/2, so the
        # half-height contour falls exactly on the true edge.
        soft = max(edge_px, 1e-6)
        return np.clip((half + soft / 2 - np.abs(distance)) / soft, 0.0, 1.0)

    heights += height_nm * ramp(along, length_px / 2) * ramp(across, width_px / 2)


def synthetic_scan(
    *,
    size_px: int = 512,
    scan_nm: float = 2000.0,
    n_rectangles: int = 40,
    length_nm: float = 191.0,
    width_nm: float = 36.0,
    height_nm: float = SHEET_HEIGHT_NM,
    n_aggregates: int = 4,
    noise_nm: float = 0.12,
    tilt_nm: float = 6.0,
    line_noise_nm: float = 0.25,
    seed: int = 0,
) -> SyntheticScan:
    """One scan, with the defects that make a real one hard.

    The tilt and line noise are not decoration. A raw AFM scan sits on a tilted
    plane because the sample is never level, and each scan line has its own
    offset because the feedback loop drifts. Flattening is the step that
    removes them, and a test image without them would let a pipeline that
    cannot flatten still pass.
    """
    rng = np.random.default_rng(seed)
    pixel_nm = scan_nm / size_px
    heights = np.zeros((size_px, size_px))
    placed: list[PlacedParticle] = []

    def free_spot(footprint_px: float) -> tuple[float, float] | None:
        for _ in range(200):
            centre = (
                float(rng.uniform(footprint_px, size_px - footprint_px)),
                float(rng.uniform(footprint_px, size_px - footprint_px)),
            )
            if all(
                np.hypot(centre[0] - p.centre_px[0], centre[1] - p.centre_px[1]) > footprint_px
                for p in placed
            ):
                return centre
        return None

    length_px, width_px = length_nm / pixel_nm, width_nm / pixel_nm
    edge_px = max(2.0, 4.0 / pixel_nm)  # a few nm of tip broadening

    # Keep centres more than a full length apart, so two rectangles cannot
    # overlap whatever their angles. With a smaller margin they sometimes
    # merge, the pipeline correctly reports one particle, and the truth still
    # claims two -- which reads as a measurement error and is not one. Crowding
    # is worth testing, but as its own scenario rather than as noise in this
    # one.
    for _ in range(n_rectangles):
        centre = free_spot(length_px * 1.1)
        if centre is None:
            break
        angle = float(rng.uniform(0, 180))
        _stamp_rectangle(
            heights,
            centre=centre,
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle,
            edge_px=edge_px,
        )
        placed.append(PlacedParticle(centre, length_nm, width_nm, height_nm, angle, "rectangle"))

    for _ in range(n_aggregates):
        centre = free_spot(length_px * 0.9)
        if centre is None:
            break
        # A clump: several overlapping blobs, taller and rounder than a sheet.
        for _ in range(rng.integers(3, 6)):
            offset = rng.normal(0, width_px * 0.6, 2)
            _stamp_rectangle(
                heights,
                centre=(centre[0] + offset[0], centre[1] + offset[1]),
                length_px=width_px * 1.4,
                width_px=width_px * 1.2,
                height_nm=height_nm * float(rng.uniform(1.8, 3.0)),
                angle_deg=float(rng.uniform(0, 180)),
                edge_px=edge_px,
            )
        placed.append(
            PlacedParticle(
                centre, width_nm * 1.8, width_nm * 1.6, height_nm * 2.4, 0.0, "aggregate"
            )
        )

    # The defects, added after the structures so they sit under everything.
    yy, xx = np.mgrid[0:size_px, 0:size_px]
    heights = heights + tilt_nm * (xx / size_px) + 0.6 * tilt_nm * (yy / size_px)
    heights = heights + rng.normal(0, line_noise_nm, (size_px, 1))  # per-line offset
    heights = heights + rng.normal(0, noise_nm, heights.shape)

    return SyntheticScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source="synthetic"),
        truth=tuple(placed),
    )

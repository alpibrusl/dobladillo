"""Finding and measuring the things on the surface.

Measurement convention, which matters more than the code: an edge is taken at
**half the particle's height**. An AFM tip is not a point, so every edge in an
image is a ramp several nanometres wide, and where you call the edge decides
the size you report. Half-height is the usual convention and it is roughly
unbiased for a ramp; thresholding near the background instead would inflate
every dimension by the tip radius.

Dimensions come from the particle's own principal axes rather than from the
image axes, for the same reason as in the trajectory analysis: an object lying
at 40 degrees has no reason to be measured along the scan direction.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: A particle must stand at least this far above the background to be counted,
#: in multiples of the background noise.
DETECT_SIGMA = 4.0

#: And must cover at least this many pixels, which keeps single noisy pixels
#: and tip debris out of the statistics.
MIN_PIXELS = 20


@dataclass(frozen=True)
class Particle:
    label: int
    centre_px: tuple[float, float]
    length_nm: float
    width_nm: float
    height_nm: float
    area_nm2: float
    angle_deg: float
    touches_edge: bool

    #: Height spread over the particle's interior, nm. A flat sheet adsorbed on
    #: mica is uniform to about the image noise; a sheet that rolled or folded
    #: carries a ridge, and the ridge shows up here before it shows up in any
    #: single dimension.
    roughness_nm: float = 0.0

    #: Filled area over the area of the particle's own bounding box, measured
    #: along its principal axes. A clean rectangle is near 1. A parallelogram,
    #: a rolled tube or a torn sheet is not, and this is what separates "the
    #: right size" from "the right shape".
    rectangularity: float = 1.0

    @property
    def aspect(self) -> float:
        return self.length_nm / self.width_nm if self.width_nm else float("inf")

    def as_dict(self) -> dict[str, Any]:
        return {
            **{
                k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in dataclasses.asdict(self).items()
            },
            "centre_px": [round(v, 1) for v in self.centre_px],
            "aspect": round(self.aspect, 2),
        }


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    from scipy import ndimage

    labels, count = ndimage.label(mask)
    return labels, int(count)


def _interior(pixels: np.ndarray) -> np.ndarray:
    """The particle minus its edge ring, chosen geometrically.

    Selecting the interior by HEIGHT looks equivalent and is not. Any
    height-based cut is computed from a noisy image, so with more noise the cut
    moves up and then selects the upper part of the noise distribution: the
    median of what survives climbs with the noise, which is the bias this is
    replacing. Eroding the mask drops the sloping edge without consulting a
    single height value, so the median of the interior is the plateau.
    """
    from scipy import ndimage

    for erosions in (3, 2, 1):
        eroded: np.ndarray = ndimage.binary_erosion(pixels, iterations=erosions)
        if eroded.sum() >= 10:
            return eroded
    return pixels


def measure_mask(
    heights: np.ndarray, pixels: np.ndarray, pixel_nm: float, label: int, shape: tuple[int, int]
) -> Particle:
    coordinates = np.column_stack(np.nonzero(pixels)).astype(float)
    centre = coordinates.mean(axis=0)
    centred = coordinates - centre

    # Same principal-axis treatment as the trajectory analysis: measure the
    # object along itself, not along the scan.
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    projected = centred @ axes.T
    extents = projected.max(axis=0) - projected.min(axis=0)
    long_px, short_px = float(extents.max()), float(extents.min())

    rows, cols = shape
    touches = bool(
        coordinates[:, 0].min() < 1
        or coordinates[:, 1].min() < 1
        or coordinates[:, 0].max() > rows - 2
        or coordinates[:, 1].max() > cols - 2
    )
    # Height is the median over the eroded interior. A high percentile of all
    # the particle's pixels looks robust and is not: with 0.12 nm of noise the
    # 90th percentile of a flat 2.00 nm plateau sits at 2.15, so the estimator
    # reads 7% high on every particle in every image.
    interior = _interior(pixels)
    height = float(np.median(heights[interior]))

    # Both measured on the eroded interior, for the same reason the height is:
    # the boundary pixels are a mixture of particle and substrate, so their
    # spread reports the edge rather than the object.
    roughness = float(np.std(heights[interior])) if interior.any() else 0.0
    box = long_px * short_px
    rectangularity = float(pixels.sum() / box) if box > 0 else 0.0

    return Particle(
        label=label,
        centre_px=(float(centre[0]), float(centre[1])),
        length_nm=long_px * pixel_nm,
        width_nm=short_px * pixel_nm,
        height_nm=height,
        area_nm2=float(pixels.sum()) * pixel_nm**2,
        angle_deg=float(np.rad2deg(np.arctan2(axes[0][0], axes[0][1])) % 180),
        touches_edge=touches,
        roughness_nm=roughness,
        rectangularity=min(rectangularity, 1.0),
    )


@dataclass(frozen=True)
class Segment:
    """One particle's pixels, and the half-height level they were cut at."""

    label: int
    mask: np.ndarray
    threshold_nm: float


def segment(
    image: HeightMap,
    background: np.ndarray,
    *,
    detect_sigma: float = DETECT_SIGMA,
    min_pixels: int = MIN_PIXELS,
    peak_percentile: float = 95.0,
) -> list[Segment]:
    """Every particle's half-height mask. `find_particles` measures these;
    `imaging.rods` traces them, so both see exactly the same pixels.

    "Its height" is the `peak_percentile` of the particle's pixels, 95 by
    default. A particle that carries marks taller than itself on more than
    5% of its area -- E8's patterned rectangle -- needs 50: its 95th
    percentile is the top of the marks, half of that can reach the sheet's
    own height, and the outline then breaks into fragments. Measured on
    synthetic 2 nm sheets with 3 nm marks under a 10 nm tip: fewer than half
    kept their outline at 95, all of them at 50 (tests/test_pattern.py).
    """
    heights = image.heights_nm
    noise = float(heights[background].std())
    seeds, _ = _label(heights > detect_sigma * noise)

    segments: list[Segment] = []
    for label in range(1, int(seeds.max()) + 1):
        seed = seeds == label
        if seed.sum() < min_pixels:
            continue
        # Re-threshold this particle at half ITS own height, so a tall
        # aggregate and a 2 nm sheet are both measured at their own half-way
        # point rather than at one global level.
        peak = float(np.percentile(heights[seed], peak_percentile))
        grown, _ = _label(heights > peak / 2.0)
        # Which grown region this particle is: the one covering most of its
        # seed -- never label 0, the substrate. A tall clump whose 95th
        # percentile is more than twice most of its pixels has most of its
        # seed BELOW its own half height, and taking the plain argmax then
        # picked the substrate: the clump became a frame-sized "particle"
        # touching the edge, was excluded, and vanished from the count. Four
        # of five synthetic aggregates did, until E9 counted them.
        overlap = np.bincount(grown[seed]) if grown[seed].size else np.zeros(1, dtype=int)
        overlap[0] = 0
        this = grown == overlap.argmax() if overlap.any() else seed
        if this.sum() < min_pixels:
            continue
        segments.append(Segment(label=label, mask=this, threshold_nm=peak / 2.0))
    return segments


def find_particles(
    image: HeightMap,
    background: np.ndarray,
    *,
    detect_sigma: float = DETECT_SIGMA,
    min_pixels: int = MIN_PIXELS,
    peak_percentile: float = 95.0,
) -> list[Particle]:
    """Everything standing proud of the surface, measured at half its height.
    See `segment` for `peak_percentile`."""
    return [
        measure_mask(image.heights_nm, s.mask, image.pixel_nm, s.label, image.shape)
        for s in segment(
            image,
            background,
            detect_sigma=detect_sigma,
            min_pixels=min_pixels,
            peak_percentile=peak_percentile,
        )
    ]

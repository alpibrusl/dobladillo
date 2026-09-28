"""Tracing elongated particles: the backbone of each rod, and what it measures.

A rectangle is measured by its outline. A rod is measured by its backbone:
how long it is along itself, how far apart its ends are, and how its
direction changes along it. None of those is a bounding-box dimension, and a
rod that bends 20 degrees is still the right rod.

**The trace.** Each particle's half-height mask (the same pixels
`particles.find_particles` measures) is thinned to a one-pixel skeleton with
scikit-image's `skeletonize` (Zhang-Suen thinning, BSD-3-Clause). The
backbone is the skeleton's longest geodesic path, found with two Dijkstra
passes from scipy; every skeleton pixel off that path belongs to a side
branch. The path is smoothed, its last half-width trimmed -- thinning curls
the skeleton into the corners of a rounded end -- and then extended straight
along its end tangent to where the height falls through the particle's own
half-height level, located to a fraction of a pixel by interpolation.

So the contour runs **half-height to half-height**, the same convention as
every other length in this project, and it is broadened at each end by the
same amount: `compare.deconvolve_tip` removes it.

**What makes a particle not a rod.** A side branch longer than
`SPUR_LIMIT_WIDTHS` times the particle's apparent width: two rods crossing,
or a rod with something stuck to it. The limit is in widths because thinning
leaves short spurs on any blunt end, about half a width long. The tangent
analysis uses only the traced part, never the straight extensions, which
carry no information about bending.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from dobladillo.imaging import wlc

if TYPE_CHECKING:
    from dobladillo.imaging.heightmap import HeightMap
    from dobladillo.imaging.particles import Segment

#: A side branch longer than this many apparent widths makes a particle
#: "branched". Thinning leaves spurs of about half a width on a blunt end;
#: two rods crossing leave branches of hundreds of nanometres. Checked on
#: synthetic crossings and single rods in tests/test_rods.py.
SPUR_LIMIT_WIDTHS = 2.0

#: Gaussian smoothing of the backbone coordinates, in apparent widths. The
#: skeleton steps between pixel centres, so an unsmoothed path zig-zags and
#: over-measures its own length by several per cent; half a width removes the
#: pixel steps and leaves bending on the scale of the rod intact.
SMOOTHING_WIDTHS = 0.5

#: Spacing of the resampled backbone, in pixels. The tangent analysis works
#: in these steps.
RESAMPLE_PX = 1.0


@dataclass(frozen=True)
class Trace:
    """One particle, traced."""

    label: int
    #: The full backbone, nm, (x, y), half-height end to half-height end.
    points_nm: np.ndarray
    #: Unwrapped tangent angles of the traced part only, at `ds_nm` spacing.
    angles_rad: np.ndarray
    ds_nm: float
    contour_nm: float
    end_to_end_nm: float
    sagitta_nm: float
    #: Median height along the backbone -- the ridge, not an eroded interior,
    #: which a rod a few pixels wide does not have.
    height_nm: float
    #: Mask area over contour: the mean half-height width.
    width_nm: float
    area_nm2: float
    longest_spur_nm: float
    touches_edge: bool

    @property
    def branched(self) -> bool:
        return self.longest_spur_nm > SPUR_LIMIT_WIDTHS * self.width_nm

    @property
    def aspect(self) -> float:
        return self.contour_nm / self.width_nm if self.width_nm else math.inf

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "contour_nm": round(self.contour_nm, 2),
            "end_to_end_nm": round(self.end_to_end_nm, 2),
            "end_to_end_ratio": round(self.end_to_end_nm / self.contour_nm, 4)
            if self.contour_nm
            else None,
            "sagitta_nm": round(self.sagitta_nm, 2),
            "height_nm": round(self.height_nm, 3),
            "width_nm": round(self.width_nm, 2),
            "aspect": round(self.aspect, 2),
            "longest_spur_nm": round(self.longest_spur_nm, 1),
            "branched": self.branched,
            "touches_edge": self.touches_edge,
        }


def _graph(skeleton: np.ndarray) -> tuple[np.ndarray, Any]:
    """The skeleton as a weighted 8-neighbour graph: pixel coordinates and a sparse matrix."""
    from scipy.sparse import coo_matrix

    coords = np.argwhere(skeleton)
    index = -np.ones(skeleton.shape, dtype=int)
    index[tuple(coords.T)] = np.arange(len(coords))
    rows, cols, weights = [], [], []
    padded = np.pad(index, 1, constant_values=-1)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            neighbour = padded[coords[:, 0] + 1 + dr, coords[:, 1] + 1 + dc]
            ok = neighbour >= 0
            rows.append(np.nonzero(ok)[0])
            cols.append(neighbour[ok])
            weights.append(np.full(ok.sum(), math.hypot(dr, dc)))
    n = len(coords)
    matrix = coo_matrix(
        (np.concatenate(weights), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)
    ).tocsr()
    return coords, matrix


def _backbone(skeleton: np.ndarray) -> tuple[np.ndarray, float]:
    """Longest geodesic path through the skeleton, and the longest branch off it (px)."""
    from scipy.sparse.csgraph import dijkstra

    coords, graph = _graph(skeleton)
    if len(coords) < 2:
        return coords.astype(float), 0.0
    first = dijkstra(graph, indices=0)
    start = int(np.argmax(np.where(np.isfinite(first), first, -1)))
    distance, previous = dijkstra(graph, indices=start, return_predecessors=True)
    end = int(np.argmax(np.where(np.isfinite(distance), distance, -1)))
    path = [end]
    while path[-1] != start and previous[path[-1]] >= 0:
        path.append(int(previous[path[-1]]))
    path_nodes = np.array(path[::-1])
    off_path = dijkstra(graph, indices=path_nodes, min_only=True)
    reachable = np.isfinite(off_path)
    spur = float(off_path[reachable].max()) if reachable.any() else 0.0
    return coords[path_nodes].astype(float), spur


def _arc_length(points: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])


def _trim(points: np.ndarray, length: float) -> np.ndarray:
    """Drop `length` of arc from each end, keeping at least a few points."""
    arc = _arc_length(points)
    if arc[-1] <= 2 * length + 2:
        return points
    keep = (arc >= length) & (arc <= arc[-1] - length)
    return np.asarray(points[keep]) if keep.sum() >= 3 else points


def _extend(
    heights: np.ndarray, points: np.ndarray, threshold: float, *, back: float, step: float = 0.25
) -> np.ndarray:
    """Where the backbone, continued straight past its last point, drops through half height.

    Direction from the last `back` pixels of arc. Heights are read by bilinear
    interpolation and the crossing located linearly between the last sample
    above the level and the first below it.
    """
    from scipy.ndimage import map_coordinates

    arc = _arc_length(points)
    anchor = points[-1]
    earlier = points[np.searchsorted(arc, max(arc[-1] - back, 0.0))]
    direction = anchor - earlier
    norm = float(np.linalg.norm(direction))
    if norm == 0:
        return np.asarray(anchor)
    direction /= norm
    limit = int(4 * back / step) + 40
    distances = np.arange(0, limit) * step
    samples = anchor[None, :] + distances[:, None] * direction[None, :]
    values = map_coordinates(heights, samples.T, order=1, mode="nearest")
    below = np.nonzero(values < threshold)[0]
    if below.size == 0 or below[0] == 0:
        return np.asarray(anchor)
    i = int(below[0])
    v0, v1 = float(values[i - 1]), float(values[i])
    fraction = (v0 - threshold) / (v0 - v1) if v0 != v1 else 0.0
    return np.asarray(anchor + (distances[i - 1] + fraction * step) * direction)


def trace(image: HeightMap, segment: Segment) -> Trace | None:
    """Trace one particle. None when its skeleton is too small to have a direction."""
    from scipy.ndimage import gaussian_filter1d
    from skimage.morphology import skeletonize

    heights = image.heights_nm
    px = image.pixel_nm
    mask = segment.mask
    rows_any, cols_any = np.nonzero(mask.any(axis=1))[0], np.nonzero(mask.any(axis=0))[0]
    r0, r1 = max(rows_any[0] - 2, 0), min(rows_any[-1] + 3, mask.shape[0])
    c0, c1 = max(cols_any[0] - 2, 0), min(cols_any[-1] + 3, mask.shape[1])
    crop = mask[r0:r1, c0:c1]
    skeleton = skeletonize(crop)  # type: ignore[no-untyped-call]
    path, spur_px = _backbone(skeleton)
    if len(path) < 3:
        return None
    path += (r0, c0)

    area_px = float(mask.sum())
    skeleton_length = float(_arc_length(path)[-1])
    width_px = area_px / max(skeleton_length, 1.0)

    sigma = max(SMOOTHING_WIDTHS * width_px, 1.0)
    smooth = np.column_stack([gaussian_filter1d(path[:, i], sigma, mode="nearest") for i in (0, 1)])
    interior = _trim(smooth, width_px / 2.0)
    interior = wlc.resample(interior, RESAMPLE_PX)
    if len(interior) < 3:
        return None
    back = max(width_px, 3.0)
    head = _extend(heights, interior[::-1], segment.threshold_nm, back=back)
    tail = _extend(heights, interior, segment.threshold_nm, back=back)
    full_px = np.vstack([head, interior, tail])

    # (row, col) px -> (x, y) nm, so angles are in the image's own frame.
    full = full_px[:, ::-1] * px
    traced = interior[:, ::-1] * px
    contour = wlc.contour_length(full)

    ridge = heights[tuple(np.round(path).astype(int).T)]
    rows, cols = mask.shape
    coordinates = np.argwhere(mask)
    touches = bool(
        coordinates[:, 0].min() < 1
        or coordinates[:, 1].min() < 1
        or coordinates[:, 0].max() > rows - 2
        or coordinates[:, 1].max() > cols - 2
    )
    return Trace(
        label=segment.label,
        points_nm=full,
        angles_rad=wlc.tangent_angles(traced),
        ds_nm=RESAMPLE_PX * px,
        contour_nm=contour,
        end_to_end_nm=wlc.end_to_end(full),
        sagitta_nm=wlc.sagitta(full),
        height_nm=float(np.median(ridge)),
        width_nm=area_px * px**2 / contour if contour else 0.0,
        area_nm2=area_px * px**2,
        longest_spur_nm=spur_px * px,
        touches_edge=touches,
    )


def trace_particles(image: HeightMap, background: np.ndarray) -> list[Trace]:
    """Every particle in a flattened image, traced."""
    from dobladillo.imaging.particles import segment

    traces = []
    for s in segment(image, background):
        traced = trace(image, s)
        if traced is not None:
            traces.append(traced)
    return traces

"""Finding a reference's marks on each particle, and saying which mark is which.

Two steps, and the second is where a calibration can quietly go wrong.

**Finding marks.** Per particle -- the half-height masks of
`imaging.particles.segment`, taken at the sheet's plateau
(`peak_percentile=50`, for the reason `segment` gives) -- the sheet level is
a low percentile of the particle's interior, and a mark is a connected region
standing above it. Two thresholds, as `imaging.pattern.read_cells` does it:
a first pass at `SPOT_SIGMA` times the background noise finds the candidates,
and the blobs are then cut at HALF the typical candidate's height. Half the
height, because a centroid is only as good as the symmetry of what it is
taken over: the upper half of a mark is the mark, while its skirt runs into
the sheet's own tip ramp near an edge and into the next mark's skirt between
cells. The centroid is weighted by the height above that cut.

**Why a centroid.** A symmetric tip adds the same skirt on every side of a
mark, so it moves the mark's edges and not its centre. A scale taken from
centroids is therefore tip-insensitive in a way a scale taken from outlines
is not (`compare.corrections` derives how much an outline moves). The tests
image the same particles with 5 and 15 nm tips and compare.

**Saying which is which.** The designed features are matched to the blobs
by fitting a similarity (rotation, one scale, translation, and a fixed
handedness) from each of eight starting poses -- the particle's long axis
from its outline, turned by 0, 90, 180 and 270 degrees, either way up --
alternating nearest-neighbour assignment and refit until the assignment
stops changing. A similarity rather than the full scanner model, because
the scanner is what is being measured: the match only has to be close
enough to pair each mark with its feature, and a few percent of anisotropy
moves no mark by more than a fraction of the spacing between them.

A particle is kept only if its best pose explains most of the designed
features AND beats every essentially different pose by a clear margin. A
wrong pairing would be fitted as a distorted scanner, so ambiguity is a
rejection, never a coin toss; `Detection.rejected` counts every reason.
Particles with no marks at all (face down, unmarked, or not a tile) are
rejected as `no_marks`, which is also how a scan of plain rectangles comes
out: no matches, and a message that says so.

Positions come out in the RASTER frame, nm: x along a scan line
(column x pixel), y down the lines (row x pixel), the frame the scanner's
errors live in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.particles import measure_mask, segment
from dobladillo.imaging.pattern import SPOT_SIGMA, background_noise_nm

if TYPE_CHECKING:
    from dobladillo.calibration.reference import ReferenceGeometry
    from dobladillo.imaging.heightmap import HeightMap

__all__ = [
    "Blob",
    "Detection",
    "ParticleMatch",
    "detect",
    "find_blobs",
    "match_particle",
]

#: The sheet level is this percentile of the particle's interior, not the
#: median: marks can cover close to half a tile under a blunt tip (12 marks,
#: each ~8 nm in radius under a 15 nm tip, on ~6000 nm2), and a median would
#: then sit on them. On a flat plateau with 0.12 nm of noise the 25th
#: percentile reads 0.08 nm low, which only moves the thresholds. Chosen.
SHEET_PERCENTILE: Final = 25.0

#: The blob cut, as a fraction of the typical mark's height above the sheet.
#: Half: see the module docstring. Chosen.
BLOB_LEVEL: Final = 0.5

#: A blob needs at least this many pixels above the cut. Chosen: below it,
#: one noisy pixel moves the centroid by a large fraction of a pixel.
MIN_BLOB_PIXELS: Final = 4

#: A mark may be matched to a feature this far from where the pose puts it,
#: as a fraction of the reference's smallest feature spacing. Chosen: under
#: a third, no mark can be nearest to two features; well above the few nm a
#: 10% scale error moves an edge mark.
MATCH_TOLERANCE: Final = 0.3

#: A particle is kept only if its best pose matches at least this fraction
#: of the designed features. Chosen: allows a couple of marks to be missing
#: (a staple that did not fold in, a hairpin swept away) and no more.
MIN_MATCHED_FRACTION: Final = 0.75

#: ...and matches at least this many more features than any essentially
#: different pose. Chosen; for the tile, the best wrong landing shares
#: 8 of 12 cells with the right one at most (Hamming distance 8 between the
#: pattern and each of its images), so a correct reading clears it by 4.
MATCH_MARGIN: Final = 3

#: Poses whose rotation differs by less than this, with the same handedness,
#: are the same pose reached twice. Degrees; chosen.
SAME_POSE_DEG: Final = 20.0

#: A similarity scale outside this range is not a miscalibrated scanner but
#: the wrong object, or the wrong pixel size. Chosen: wider than any lateral
#: miscalibration an instrument in service is likely to have.
SCALE_RANGE: Final = (0.75, 1.33)

#: Rounds of re-centring a mark's disc on its own centroid. Chosen: the
#: shift after the second is far below a pixel.
REFINE_ROUNDS: Final = 3

#: Nearest-neighbour / refit rounds per starting pose. Chosen; convergence
#: takes two or three.
ICP_ROUNDS: Final = 12


@dataclass(frozen=True)
class Blob:
    """One mark as imaged: its centroid (row, col, in pixels) and height."""

    centre_px: tuple[float, float]
    peak_nm: float
    pixels: int


@dataclass(frozen=True)
class ParticleMatch:
    """One particle's marks, each paired with the feature it is.

    `design_nm` are the reference positions (object frame), `observed_nm`
    the centroids (raster frame, nm), row for row. `handedness` is the sign
    of the pose's determinant in the raster frame (+1: the particle is seen
    as the object is drawn with y DOWN; -1: with y up, i.e. marks-up for the
    tile). `angle_deg`, `scale` and `rms_nm` are from the similarity fit.
    """

    image: int
    label: int
    names: tuple[str, ...]
    design_nm: np.ndarray
    observed_nm: np.ndarray
    handedness: int
    angle_deg: float
    scale: float
    rms_nm: float
    blobs: int

    @property
    def n(self) -> int:
        return len(self.names)

    def as_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "label": self.label,
            "matched": self.n,
            "blobs": self.blobs,
            "handedness": self.handedness,
            "angle_deg": round(self.angle_deg, 2),
            "similarity_scale": round(self.scale, 4),
            "similarity_rms_nm": round(self.rms_nm, 3),
        }


@dataclass(frozen=True)
class Detection:
    """Everything one image gave: the matched particles and why the rest were not."""

    matches: tuple[ParticleMatch, ...]
    rejected: dict[str, int] = field(default_factory=dict)
    particles: int = 0
    noise_nm: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "particles": self.particles,
            "matched": len(self.matches),
            "rejected": dict(sorted(self.rejected.items())),
            "noise_nm": round(self.noise_nm, 4),
        }


def find_blobs(
    heights: np.ndarray,
    mask: np.ndarray,
    *,
    noise_nm: float,
    pixel_nm: float,
    reach_nm: float,
    window_nm: float,
) -> list[Blob]:
    """The marks on one particle. See the module docstring.

    `mask` is the particle's half-height outline; marks are looked for in it
    grown by `reach_nm`, so that a mark's upper half is not cut by the
    outline. `window_nm` caps the disc a centroid is refined over; `detect`
    passes half the reference's smallest feature spacing.
    """
    from scipy import ndimage

    window_px = window_nm / pixel_nm
    rows = np.nonzero(mask.any(axis=1))[0]
    cols = np.nonzero(mask.any(axis=0))[0]
    grow = int(math.ceil(reach_nm / pixel_nm)) + 2
    r0, r1 = max(0, rows[0] - grow), min(mask.shape[0], rows[-1] + grow + 1)
    c0, c1 = max(0, cols[0] - grow), min(mask.shape[1], cols[-1] + grow + 1)
    h = heights[r0:r1, c0:c1]
    m = mask[r0:r1, c0:c1]
    interior = ndimage.binary_erosion(m, iterations=3)
    if interior.sum() < 10:
        interior = m
    sheet = float(np.percentile(h[interior], SHEET_PERCENTILE))
    excess = h - sheet
    region = ndimage.binary_dilation(m, iterations=grow)
    smooth = ndimage.gaussian_filter(excess, 1.0)

    first = region & (smooth > SPOT_SIGMA * noise_nm)
    labels, count = ndimage.label(first)
    if count == 0:
        return []
    peaks = np.asarray(ndimage.maximum(smooth, labels, index=np.arange(1, count + 1)))
    sizes = np.bincount(labels.ravel())[1:]
    real = peaks[sizes >= MIN_BLOB_PIXELS]
    if real.size == 0:
        return []
    level = max(SPOT_SIGMA * noise_nm, BLOB_LEVEL * float(np.median(real)))

    labels, count = ndimage.label(region & (smooth > level))
    rr, cc = np.mgrid[0 : h.shape[0], 0 : h.shape[1]]
    weight = np.clip(excess - level, 0.0, None)
    found: list[tuple[np.ndarray, float, int]] = []
    for k in range(1, count + 1):
        inside = labels == k
        if inside.sum() < MIN_BLOB_PIXELS:
            continue
        w = weight[inside]
        if float(w.sum()) <= 0:
            continue
        centre = np.array([(rr[inside] * w).sum(), (cc[inside] * w).sum()]) / float(w.sum())
        found.append((centre, float(smooth[inside].max()), int(inside.sum())))

    # Refine each centroid over a DISC centred on itself, half the distance
    # to its nearest neighbour across, with the raw (unsmoothed) excess. The
    # component above is cut on the smoothed image, and near a sheet edge the
    # smoothing mixes in the sheet's own ramp, so its boundary is not
    # symmetric about the mark; a disc about the centroid is. Measured on
    # synthetic tiles, this removed a 0.03% under-reading of the object's
    # width that the component centroid carried.
    centres = np.array([c for c, _, _ in found]).reshape(-1, 2)
    blobs = []
    for i, (centre, peak, size) in enumerate(found):
        others = np.delete(centres, i, axis=0)
        nearest = float(np.hypot(*(others - centre).T).min()) if len(others) else np.inf
        radius = min(window_px, nearest / 2.0)
        for _ in range(REFINE_ROUNDS):
            disc = np.hypot(rr - centre[0], cc - centre[1]) <= radius
            w = weight[disc]
            if float(w.sum()) <= 0:
                break
            centre = np.array([(rr[disc] * w).sum(), (cc[disc] * w).sum()]) / float(w.sum())
        row, col = float(centre[0]) + r0, float(centre[1]) + c0
        # The mark must stand on this particle: one hanging over from a
        # neighbour, beyond the outline, is not its.
        inside_outline = mask[
            min(max(round(row), 0), mask.shape[0] - 1), min(max(round(col), 0), mask.shape[1] - 1)
        ]
        if inside_outline:
            blobs.append(Blob(centre_px=(row, col), peak_nm=peak, pixels=size))
    return blobs


@dataclass(frozen=True)
class _Pose:
    handedness: int
    angle: float  # radians, raster frame
    scale: float
    translation: np.ndarray
    pairs: tuple[tuple[int, int], ...]  # (feature index, blob index)
    rms: float

    def matrix(self) -> np.ndarray:
        c, s = math.cos(self.angle), math.sin(self.angle)
        rotation: np.ndarray = (
            self.scale * np.array([[c, -s], [s, c]]) @ np.diag([1.0, float(self.handedness)])
        )
        return rotation


def _similarity(q: np.ndarray, p: np.ndarray, handedness: int) -> tuple[float, float, np.ndarray]:
    """Least-squares p ~ s R(theta) diag(1, h) q + t (Umeyama 1991, 2D, reflection fixed)."""
    q = q * np.array([1.0, float(handedness)])
    qc, pc = q - q.mean(axis=0), p - p.mean(axis=0)
    # For 2D, the optimal angle is atan2 of the cross and dot sums.
    dot = float((qc * pc).sum())
    cross = float((qc[:, 0] * pc[:, 1] - qc[:, 1] * pc[:, 0]).sum())
    angle = math.atan2(cross, dot)
    scale = math.hypot(dot, cross) / float((qc**2).sum())
    c, s = math.cos(angle), math.sin(angle)
    t = p.mean(axis=0) - scale * (np.array([[c, -s], [s, c]]) @ q.mean(axis=0))
    return angle, scale, t


def _refine(design: np.ndarray, observed: np.ndarray, pose: _Pose, tolerance: float) -> _Pose:
    """Alternate mutual-nearest assignment and similarity refit."""
    pairs: tuple[tuple[int, int], ...] = ()
    for _ in range(ICP_ROUNDS):
        predicted = design @ pose.matrix().T + pose.translation
        d = np.hypot(*(predicted[:, None, :] - observed[None, :, :]).transpose(2, 0, 1))
        nearest_blob = d.argmin(axis=1)
        nearest_feature = d.argmin(axis=0)
        new = tuple(
            (i, int(j))
            for i, j in enumerate(nearest_blob)
            if d[i, j] < tolerance and nearest_feature[j] == i
        )
        if len(new) < 3:
            return _Pose(pose.handedness, pose.angle, pose.scale, pose.translation, new, math.inf)
        fi = [i for i, _ in new]
        bj = [j for _, j in new]
        angle, scale, t = _similarity(design[fi], observed[bj], pose.handedness)
        pose = _Pose(pose.handedness, angle, scale, t, new, 0.0)
        if new == pairs:
            break
        pairs = new
    fi = [i for i, _ in pose.pairs]
    bj = [j for _, j in pose.pairs]
    residual = design[fi] @ pose.matrix().T + pose.translation - observed[bj]
    rms = float(np.sqrt((residual**2).sum(axis=1).mean()))
    return _Pose(pose.handedness, pose.angle, pose.scale, pose.translation, pose.pairs, rms)


def match_particle(
    blobs_nm: np.ndarray,
    reference: ReferenceGeometry,
    *,
    centre_nm: np.ndarray,
    axis_deg: float,
) -> tuple[_Pose | None, str]:
    """The pose that pairs these blobs with the reference's features, or why not.

    `blobs_nm` are centroids in the raster frame, nm; `centre_nm` and
    `axis_deg` the particle's outline centre and long-axis angle (as
    `Particle.angle_deg`: from +column towards +row). Returns the pose and
    "ok", or None and the rejection reason.
    """
    design = reference.positions_nm - reference.positions_nm.mean(axis=0)
    n = len(design)
    if len(blobs_nm) == 0:
        return None, "no_marks"
    if len(blobs_nm) < 3:
        return None, "too_few_marks"
    tolerance = MATCH_TOLERANCE * reference.min_spacing_nm
    starts = [centre_nm, blobs_nm.mean(axis=0)]
    poses: list[_Pose] = []
    for handedness in (1, -1):
        for turn in (0.0, 90.0, 180.0, 270.0):
            for start in starts:
                pose = _Pose(
                    handedness=handedness,
                    angle=math.radians(axis_deg + turn),
                    scale=1.0,
                    translation=np.asarray(start, dtype=float),
                    pairs=(),
                    rms=math.inf,
                )
                poses.append(_refine(design, blobs_nm, pose, tolerance))
    poses.sort(key=lambda p: (-len(p.pairs), p.rms))
    best = poses[0]

    def same(a: _Pose, b: _Pose) -> bool:
        diff = (math.degrees(a.angle - b.angle) + 180.0) % 360.0 - 180.0
        return a.handedness == b.handedness and abs(diff) < SAME_POSE_DEG

    rivals = [p for p in poses if not same(p, best)]
    runner_up = max((len(p.pairs) for p in rivals), default=0)
    if len(best.pairs) < max(3, math.ceil(MIN_MATCHED_FRACTION * n)):
        return None, "too_few_matched"
    if len(best.pairs) - runner_up < MATCH_MARGIN:
        return None, "ambiguous"
    if not SCALE_RANGE[0] <= best.scale <= SCALE_RANGE[1]:
        return None, "scale_out_of_range"
    if best.rms > tolerance / 2.0:
        return None, "poor_fit"
    return best, "ok"


def detect(
    image: HeightMap,
    reference: ReferenceGeometry,
    *,
    image_index: int = 0,
    tip_reach_nm: float = 12.0,
) -> Detection:
    """Flatten one scan, find its particles and match each to the reference.

    `tip_reach_nm` is how far beyond a particle's outline to look for the
    upper half of a mark; the default covers a 20 nm tip on 2 nm marks.
    """
    levelled, background = flatten(image)
    noise = background_noise_nm(levelled, background)
    heights = levelled.heights_nm
    pixel = levelled.pixel_nm
    rejected: dict[str, int] = {}
    matches: list[ParticleMatch] = []
    segments = segment(levelled, background, peak_percentile=50)
    for seg in segments:
        particle = measure_mask(heights, seg.mask, pixel, seg.label, levelled.shape)
        if particle.touches_edge:
            rejected["touches_edge"] = rejected.get("touches_edge", 0) + 1
            continue
        blobs = find_blobs(
            heights,
            seg.mask,
            noise_nm=noise,
            pixel_nm=pixel,
            reach_nm=tip_reach_nm,
            window_nm=0.5 * reference.min_spacing_nm,
        )
        observed = np.array([[b.centre_px[1] * pixel, b.centre_px[0] * pixel] for b in blobs])
        centre = np.array([particle.centre_px[1] * pixel, particle.centre_px[0] * pixel])
        pose, reason = match_particle(
            observed.reshape(-1, 2), reference, centre_nm=centre, axis_deg=particle.angle_deg
        )
        if pose is None:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        fi = [i for i, _ in pose.pairs]
        bj = [j for _, j in pose.pairs]
        matches.append(
            ParticleMatch(
                image=image_index,
                label=seg.label,
                names=tuple(reference.names[i] for i in fi),
                design_nm=reference.positions_nm[fi],
                observed_nm=observed[bj],
                handedness=pose.handedness,
                angle_deg=math.degrees(pose.angle) % 360.0,
                scale=pose.scale,
                rms_nm=pose.rms,
                blobs=len(blobs),
            )
        )
    return Detection(
        matches=tuple(matches), rejected=rejected, particles=len(segments), noise_nm=noise
    )

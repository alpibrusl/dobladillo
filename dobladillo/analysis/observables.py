"""Turning a trajectory into numbers that have experimental counterparts.

Every observable here was chosen because something in a microscope can be
compared against it. A quantity with no measurable counterpart is not an
observable for this project's purposes, however easy it is to compute.

One decision worth stating. Dimensions are measured **per frame and then
averaged**, not measured once on an averaged structure. Averaging structures
requires superimposing them, superimposing requires a reference, and a badly
chosen reference quietly biases the result. Measuring each frame independently
needs no reference at all, and it yields a spread as well as a mean -- and the
spread is the thing an AFM histogram can actually be compared against.

What is NOT computed here. The fluctuation needs superimposition, and
superimposition is a commodity this project once got wrong (the Kabsch
transpose). Mean structure and RMSF therefore come from oxDNA_analysis_tools
through `analysis._oat`; this module keeps the observables no tool provides
and the guard on how many frames they rest on.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.analysis import _oat

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from dobladillo.analysis.trajectory import Frame

#: Extents are taken between these percentiles rather than between the extreme
#: nucleotides. A single frayed end would otherwise add nanometres to a
#: dimension that an AFM image, which sees the body of the object, would not.
EXTENT_PERCENTILES = (1.0, 99.0)


@dataclass(frozen=True)
class Spread:
    """A quantity measured across frames: mean, spread, and how many."""

    mean: float
    sd: float
    n: int

    def as_dict(self) -> dict[str, float | int]:
        return {"mean": round(self.mean, 3), "sd": round(self.sd, 3), "frames": self.n}

    def agrees_with(self, expected: float, *, within: float) -> bool:
        """Is `expected` within `within` (as a fraction) of the mean?"""
        return abs(self.mean - expected) <= within * expected


def principal_extents_nm(positions_nm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Extent along each principal axis, longest first, plus the axes.

    The object's own axes rather than the box's: a structure free to tumble has
    no reason to lie along x, and measuring along the box would report a size
    that changes as it rotates.

    "Longest first" needs the sort below, and that is not pedantry. SVD orders
    axes by VARIANCE, and for a straight object the axis of greatest variance
    is also the one of greatest extent, so the two orderings agree and the
    difference is invisible. For a bent one they come apart: the hinge at a
    4 nt joint reported a "longest" of 76.6 nm and a "middle" of 79.4 nm,
    which is not a measurement error but a mislabelling, and it is the kind
    that survives review because each number is individually right.
    """
    centred = positions_nm - positions_nm.mean(axis=0)
    # SVD rather than an explicit covariance eigendecomposition: same axes,
    # better conditioned on nearly flat or nearly linear structures, which is
    # exactly what a sheet and a bundle are.
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    projected = centred @ axes.T
    low, high = np.percentile(projected, EXTENT_PERCENTILES, axis=0)
    extents = high - low
    order = np.argsort(extents)[::-1]
    return extents[order], axes[order]


def planarity_nm(positions_nm: np.ndarray) -> float:
    """RMS distance from the best-fit plane.

    For a flat sheet this is the number that carries the twist correction: a
    rectangle whose lattice mismatch was not cancelled does not lie flat, and
    that is exactly what shows in an AFM image of it on mica.
    """
    centred = positions_nm - positions_nm.mean(axis=0)
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    return float(np.sqrt((centred @ axes[2]) ** 2).mean())


def axis_bend_nm(positions_nm: np.ndarray, *, bins: int = 20) -> float:
    """How far the object's centre line strays from straight.

    For a bundle: slice along the long axis, take the centroid of each slice,
    and report the largest distance from the straight line joining the ends.
    A stiff strut should be close to zero; a floppy one should not.
    """
    centred = positions_nm - positions_nm.mean(axis=0)
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    along = centred @ axes[0]
    edges = np.linspace(along.min(), along.max(), bins + 1)
    centroids = []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        inside = (along >= low) & (along <= high)
        if inside.sum() > 2:
            centroids.append(centred[inside].mean(axis=0))
    if len(centroids) < 3:
        return 0.0
    path = np.stack(centroids)

    start, end = path[0], path[-1]
    direction = end - start
    length = np.linalg.norm(direction)
    if length == 0:
        return 0.0
    direction = direction / length
    offsets = path - start
    perpendicular = offsets - np.outer(offsets @ direction, direction)
    return float(np.linalg.norm(perpendicular, axis=1).max())


#: Frames below which an RMSF should not be quoted without a warning.
#: Derived, not chosen: the relative standard error of a spread estimated from
#: n independent samples is about 1/sqrt(2(n-1)), so 10% needs n = 51. It is
#: optimistic even so, because MD frames are correlated and the effective
#: sample size is below the frame count; treat it as a floor, not a target.
FRAMES_FOR_A_TRUSTWORTHY_RMSF: Final = 50


@dataclass(frozen=True)
class Report:
    frames: int
    first_step: int
    last_step: int
    nucleotides: int
    dimensions_nm: dict[str, Spread]
    planarity_nm: Spread
    bend_nm: Spread
    rmsf_nm: np.ndarray
    potential_energy: Spread
    #: oat's mean structure, centred, nm. None for a single frame, where there
    #: is nothing to average and the frame is the structure.
    mean_structure_nm: np.ndarray | None = None

    @property
    def undersampled(self) -> bool:
        """Whether the spreads in this report are worth believing.

        A four-frame trajectory produces an RMSF, a standard deviation and a
        confident-looking dictionary. Saying so here is the difference between
        a thin result and a wrong one.
        """
        return self.frames < FRAMES_FOR_A_TRUSTWORTHY_RMSF

    def as_dict(self) -> dict[str, Any]:
        return {
            "frames": self.frames,
            "undersampled": self.undersampled,
            "steps": {"first": self.first_step, "last": self.last_step},
            "nucleotides": self.nucleotides,
            "dimensions_nm": {k: v.as_dict() for k, v in self.dimensions_nm.items()},
            "planarity_nm": self.planarity_nm.as_dict(),
            "bend_nm": self.bend_nm.as_dict(),
            "rmsf_nm": {
                "mean": round(float(self.rmsf_nm.mean()), 3),
                "max": round(float(self.rmsf_nm.max()), 3),
                "per_nucleotide": "written separately as an oxView overlay",
                "relative_standard_error": (
                    round((2 * (self.frames - 1)) ** -0.5, 3) if self.frames > 1 else None
                ),
                "computed_by": _oat.provenance() if self.mean_structure_nm is not None else None,
            },
            "potential_energy_per_nucleotide": self.potential_energy.as_dict(),
        }


def _spread(values: Sequence[float]) -> Spread:
    array = np.asarray(values, dtype=float)
    return Spread(
        float(array.mean()), float(array.std(ddof=1)) if array.size > 1 else 0.0, int(array.size)
    )


def separation_nm(frames: Sequence[Frame], a: Sequence[int], b: Sequence[int]) -> Spread:
    """Distance between the centroids of two groups of particles, over frames.

    Centroids rather than closest approach: a closest-approach distance is
    dominated by whichever single nucleotide happens to fluctuate furthest,
    and reads shorter than the group ever actually is.
    """
    if not a or not b:
        raise ValueError("both groups need at least one particle")
    if not frames:
        raise ValueError("no frames")
    distances = []
    for frame in frames:
        positions = frame.positions_nm
        if max(max(a), max(b)) >= len(positions):
            raise ValueError(
                f"particle index out of range: the trajectory has {len(positions)} "
                "particles, which is not the design these indices came from"
            )
        distances.append(
            float(np.linalg.norm(positions[list(a)].mean(axis=0) - positions[list(b)].mean(axis=0)))
        )
    return _spread(distances)


@dataclass(frozen=True)
class Reach:
    """Whether two unpaired extensions ever come close enough to bind."""

    separation: Spread
    closest_nm: float
    span_nm: float

    @property
    def within_reach(self) -> bool:
        """Necessary, not sufficient.

        `span_nm` is the two extensions' combined CONTOUR length, so this asks
        whether they could touch if both were pulled straight. A real coil is
        much shorter, and straightening it costs entropy the latch's binding
        energy must pay for. A False here is decisive -- the mechanism cannot
        close. A True is permission to look further, not a prediction.
        """
        return self.closest_nm <= self.span_nm

    def as_dict(self) -> dict[str, Any]:
        return {
            "separation_nm": self.separation.as_dict(),
            "closest_nm": round(self.closest_nm, 2),
            "reach_span_nm": round(self.span_nm, 2),
            "within_reach": self.within_reach,
            "caveat": "contour length, so necessary and not sufficient",
        }


def reach(frames: Sequence[Frame], a: Sequence[int], b: Sequence[int], *, bases: int) -> Reach:
    """Can these two extensions, of `bases` each, meet in this trajectory?"""
    from dobladillo.constants import SSDNA_RISE_PER_BASE_NM

    spread = separation_nm(frames, a, b)
    closest = min(
        float(
            np.linalg.norm(
                f.positions_nm[list(a)].mean(axis=0) - f.positions_nm[list(b)].mean(axis=0)
            )
        )
        for f in frames
    )
    return Reach(
        separation=spread,
        closest_nm=closest,
        span_nm=2 * bases * SSDNA_RISE_PER_BASE_NM,
    )


def analyse(frames: Sequence[Frame], *, trajectory: Path, skip: int = 0) -> Report:
    """Every observable, from a list of frames and the file they were read from.

    `frames` are what `read_trajectory(trajectory, skip=skip)` returned. The
    per-frame observables are measured on them; the fluctuation is computed by
    oat from the same file with the same `skip`. That is two independent
    parsers of one file, so they are made to agree on the frame and nucleotide
    counts before either number is reported -- a mismatch means the frames did
    not come from this trajectory, and the RMSF would belong to something else.
    """
    if not frames:
        raise ValueError("no frames to analyse")

    longest, middle, shortest = [], [], []
    flatness, bends, energies = [], [], []
    for frame in frames:
        extents, _ = principal_extents_nm(frame.positions_nm)
        longest.append(extents[0])
        middle.append(extents[1])
        shortest.append(extents[2])
        flatness.append(planarity_nm(frame.positions_nm))
        bends.append(axis_bend_nm(frame.positions_nm))
        energies.append(frame.energy[1])

    # One frame has no fluctuation to measure: zero by definition, not by
    # measurement, and `undersampled` already says so.
    fluctuation = np.zeros(frames[0].nucleotides)
    mean_structure = None
    if len(frames) > 1:
        oat = _oat.deviations(trajectory, skip=skip)
        if (oat.frames, oat.nucleotides) != (len(frames), frames[0].nucleotides):
            raise ValueError(
                f"oat read {oat.frames} frames of {oat.nucleotides} nucleotides from "
                f"{trajectory} after skipping {skip}, but {len(frames)} frames of "
                f"{frames[0].nucleotides} were passed in: they are not the same trajectory"
            )
        fluctuation, mean_structure = oat.rmsf_nm, oat.mean_structure_nm

    return Report(
        frames=len(frames),
        first_step=frames[0].step,
        last_step=frames[-1].step,
        nucleotides=frames[0].nucleotides,
        dimensions_nm={
            "longest": _spread(longest),
            "middle": _spread(middle),
            "shortest": _spread(shortest),
        },
        planarity_nm=_spread(flatness),
        bend_nm=_spread(bends),
        rmsf_nm=fluctuation,
        potential_energy=_spread(energies),
        mean_structure_nm=mean_structure,
    )


def oxview_overlay(values: np.ndarray) -> list[float]:
    """Per-nucleotide numbers in the shape oxView colours a structure with."""
    return [round(float(v), 4) for v in values]


#: Keep for the record: dataclasses.asdict on Report would choke on the numpy
#: array, which is why as_dict is written out rather than generated.
_ = dataclasses

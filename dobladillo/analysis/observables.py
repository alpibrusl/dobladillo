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
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def _kabsch(mobile: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Matrix M such that `mobile @ M` best superimposes onto `reference`.

    Points are stored as ROWS here, which flips the convention: the textbook
    Kabsch rotation R satisfies q = R p for column vectors, so the row form is
    its transpose, U V^T rather than V U^T. Getting that backwards produces a
    valid rotation matrix that rotates the wrong way, and the only symptom is
    an RMSF far too large -- which is how this was caught, by asking for the
    fluctuation of a rigid body that merely tumbles.
    """
    covariance = mobile.T @ reference
    u, _, vt = np.linalg.svd(covariance)
    # Guard against a reflection, which would superimpose a mirror image and
    # report a suspiciously good fit for a structure that is nothing like it.
    sign = np.sign(np.linalg.det(u @ vt))
    correction = np.diag([1.0, 1.0, sign])
    return u @ correction @ vt


def rmsf_nm(frames: Sequence[Frame]) -> tuple[np.ndarray, np.ndarray]:
    """Per-nucleotide fluctuation about the mean structure, and that structure.

    Needs superimposition, unlike the dimensions: otherwise the object's own
    tumbling swamps the internal motion this is trying to measure. Iterated
    once, using the first frame as the initial reference and the resulting mean
    as the second, which is enough to stop the answer depending on which frame
    happened to be first.
    """
    if len(frames) < 2:
        raise ValueError("RMSF needs at least two frames")

    centred = [f.positions_nm - f.positions_nm.mean(axis=0) for f in frames]
    reference = centred[0]
    for _ in range(2):
        aligned = np.stack([c @ _kabsch(c, reference) for c in centred])
        reference = aligned.mean(axis=0)

    displacement = aligned - reference
    return np.sqrt((displacement**2).sum(axis=2).mean(axis=0)), reference


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
            },
            "potential_energy_per_nucleotide": self.potential_energy.as_dict(),
        }


def _spread(values: Sequence[float]) -> Spread:
    array = np.asarray(values, dtype=float)
    return Spread(
        float(array.mean()), float(array.std(ddof=1)) if array.size > 1 else 0.0, int(array.size)
    )


def analyse(frames: Sequence[Frame]) -> Report:
    """Every observable, from a list of frames."""
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

    fluctuation, _ = rmsf_nm(frames) if len(frames) > 1 else (np.zeros(frames[0].nucleotides), None)

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
    )


def oxview_overlay(values: np.ndarray) -> list[float]:
    """Per-nucleotide numbers in the shape oxView colours a structure with."""
    return [round(float(v), 4) for v in values]


#: Keep for the record: dataclasses.asdict on Report would choke on the numpy
#: array, which is why as_dict is written out rather than generated.
_ = dataclasses

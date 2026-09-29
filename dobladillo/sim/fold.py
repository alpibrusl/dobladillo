"""Folding a relaxed configuration: rotating part of it, rigidly, about an axis.

The hinge sweep (#17) ran four joints from the open, as-designed shape for
about 9 ns and never saw the arms close; closing is rare on that timescale.
So the question "does the latch hold the closed state?" has to be asked from
a closed start. This module makes one: it takes a relaxed configuration and
turns arm B about the joint until it lies over arm A.

The conf format, from oxDNA's documentation: a three-line header (`t =`,
`b =`, `E =`), then one line per nucleotide of fifteen numbers -- position
r, the backbone-to-base versor a1, the base normal a3, velocity v and angular
velocity L. A rigid rotation turns r about the axis and turns a1, a3, v and L
as vectors. Forget a1 and a3 and every moved base keeps pointing the way it
did before the move: the helices would be intact in position and unpaired in
orientation, and oxDNA would see a melted arm.

What this does NOT do is repair the joint. Its single strands are swung along
a fraction of the rotation each, which keeps their chain in order, but the
bonds at each end are stretched or compressed; the relaxation's Monte Carlo
stage, with capped backbone forces, is what makes that physical again.
No force is put between the latch halves: whether they find each other is the
question being asked.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.units import nm_to_oxdna, oxdna_to_nm

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladillo.parts.hinge import HingeParticles

#: Columns per nucleotide in an oxDNA configuration, and where each vector is.
FIELDS: Final = 15
POSITION: Final = slice(0, 3)
VECTORS: Final = (slice(3, 6), slice(6, 9), slice(9, 12), slice(12, 15))


@dataclass(frozen=True)
class Configuration:
    """One oxDNA configuration: the three header lines and the particle table."""

    header: tuple[str, str, str]
    data: np.ndarray

    @property
    def box(self) -> np.ndarray:
        return np.fromstring(self.header[1].split("=")[1], sep=" ")

    def write(self, path: Path) -> None:
        rows = "\n".join(" ".join(repr(float(x)) for x in row) for row in self.data)
        path.write_text("\n".join(self.header) + "\n" + rows + "\n")


def read_configuration(path: Path) -> Configuration:
    """The first configuration in a conf or trajectory file."""
    lines = path.read_text().splitlines()
    if len(lines) < 4 or not lines[0].startswith("t ="):
        raise ValueError(f"{path} is not an oxDNA configuration")
    rows = []
    for line in lines[3:]:
        if line.startswith("t ="):
            break
        if line.strip():
            rows.append(line)
    data = np.fromstring(" ".join(rows), sep=" ")
    if data.size % FIELDS:
        raise ValueError(f"{path}: {data.size} numbers is not {FIELDS} per nucleotide")
    return Configuration((lines[0], lines[1], lines[2]), data.reshape(-1, FIELDS))


def rotation_matrix(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    """Right-handed rotation by `angle_rad` about `axis` (Rodrigues)."""
    u = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(u)
    if norm == 0:
        raise ValueError("the rotation axis has zero length")
    u = u / norm
    k = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return np.asarray(np.eye(3) + np.sin(angle_rad) * k + (1 - np.cos(angle_rad)) * (k @ k))


def rotate_particles(
    data: np.ndarray,
    indices: Sequence[int],
    *,
    point: np.ndarray,
    axis: np.ndarray,
    angle_rad: float,
) -> np.ndarray:
    """A copy of `data` with `indices` turned rigidly about the axis through `point`.

    Positions rotate about the axis; a1, a3, velocity and angular velocity
    rotate as vectors. `point` is in the configuration's own units.
    """
    out = np.array(data, dtype=float, copy=True)
    idx = np.asarray(indices, dtype=int)
    if idx.size == 0:
        return out
    rotation = rotation_matrix(axis, angle_rad)
    origin = np.asarray(point, dtype=float)
    out[idx, POSITION] = (data[idx, POSITION] - origin) @ rotation.T + origin
    for columns in VECTORS:
        out[idx, columns] = data[idx, columns] @ rotation.T
    return out


#: Closest centre-to-centre distance allowed between a nucleotide of one
#: folded arm and one of the other, nm. Neighbouring helices in one arm sit
#: ~2.6 nm apart axis to axis and their nucleotide centres no closer than
#: ~1 nm; this asks the same of the two arms, so the fold starts without
#: overlaps for the Monte Carlo stage to push apart -- and, more to the
#: point, without one arm's helices threaded through the other's, which no
#: relaxation undoes.
CLEARANCE_NM: Final = 1.0

#: The gap search between the folded arms, nm. It starts below one helix
#: diameter (~2 nm) on purpose, so the answer is set by the clearance rather
#: than by the starting value. Relaxed arms are not flat -- the hinge's twist
#: and ripple a sheet by several nm corner to corner (2026-09-29, the joint
#: sweep's production frames) -- so two stacked rigidly need a gap of 5-10 nm.
GAP_START_NM: Final = 1.5
GAP_STEP_NM: Final = 0.25
GAP_MAX_NM: Final = 15.0


@dataclass(frozen=True)
class HingeFold:
    """A folded hinge configuration and how it was made."""

    data: np.ndarray
    rotation_deg: float
    side: int
    opening_target_deg: float
    gap_nm: float
    closest_nm: float
    opening_before_deg: float
    opening_after_deg: float
    anchor_distance_before_nm: float
    anchor_distance_after_nm: float
    axis_point: np.ndarray
    axis: np.ndarray

    def as_dict(self) -> dict[str, Any]:
        return {
            "rotation_deg": round(self.rotation_deg, 2),
            "side": self.side,
            "opening_target_deg": self.opening_target_deg,
            "gap_nm": round(self.gap_nm, 2),
            "closest_between_arms_nm": round(self.closest_nm, 3),
            "opening_before_deg": round(self.opening_before_deg, 2),
            "opening_after_deg": round(self.opening_after_deg, 2),
            "latch_anchor_distance_before_nm": round(self.anchor_distance_before_nm, 2),
            "latch_anchor_distance_after_nm": round(self.anchor_distance_after_nm, 2),
            "axis_point_oxdna": [round(float(x), 4) for x in self.axis_point],
            "axis": [round(float(x), 5) for x in self.axis],
        }


def _unit(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if norm == 0:
        raise ValueError("degenerate geometry: a direction has zero length")
    return np.asarray(v / norm)


def _opening(positions: np.ndarray, particles: HingeParticles) -> float:
    from dobladillo.analysis.observables import hinge_opening_deg

    return hinge_opening_deg(
        positions,
        arm_a=particles.arm_a,
        edge_a=particles.edge_a,
        arm_b=particles.arm_b,
        edge_b=particles.edge_b,
    )


def fold_hinge(
    data: np.ndarray,
    particles: HingeParticles,
    *,
    opening_deg: float = 0.0,
    side: int | None = None,
    clearance_nm: float = CLEARANCE_NM,
) -> HingeFold:
    """Turn arm B about the joint until it lies over arm A, `opening_deg` apart.

    The axis runs along the joint, across the helices: the first principal
    direction of the two arms' joint-side edge bands together. It passes
    through the midpoint of the two bands, lifted by half the gap toward the
    side arm B folds to, so that a half turn lands arm B one gap above arm A
    rather than inside it. The gap is the smallest, in GAP_STEP_NM steps, at
    which no nucleotide of one arm is within `clearance_nm` of the other
    (latch extensions aside: they dangle, and whether they meet is the
    question). Raises when no gap up to GAP_MAX_NM clears.

    `side` is which face of arm A arm B folds onto: +1 is the side of the
    axis (pointing toward the latch anchor's end of the joint) crossed with
    arm A's direction, -1 the other. None takes the short way round
    from the starting shape. `opening_deg` tilts arm B away from arm A by that
    much about the same axis. The joint's single strands turn by their
    fraction along the joint times the full rotation.

    `data` is in oxDNA units, as read; so is the result.
    """
    from scipy.spatial import cKDTree

    positions = np.asarray(data[:, POSITION], dtype=float)
    arm_a = np.asarray(particles.arm_a, dtype=int)
    arm_b = np.asarray(particles.arm_b, dtype=int)
    edge_a = np.asarray(particles.edge_a, dtype=int)
    edge_b = np.asarray(particles.edge_b, dtype=int)
    edges = np.concatenate([edge_a, edge_b])

    centred = positions[edges] - positions[edges].mean(axis=0)
    axis = _unit(np.linalg.svd(centred, full_matrices=False)[2][0])
    pivot = 0.5 * (positions[edge_a].mean(axis=0) + positions[edge_b].mean(axis=0))
    # A principal axis has no sign of its own, and `side` is defined through
    # it; point it toward the latch's end of the joint so a side means the
    # same face every time.
    if axis @ (positions[particles.anchor_a] - pivot) < 0:
        axis = -axis

    def perpendicular(v: np.ndarray) -> np.ndarray:
        return _unit(v - (v @ axis) * axis)

    # Each arm's direction as `hinge_opening_deg` measures it -- edge band to
    # centroid -- so the angle the fold aims for is the angle then measured.
    a_dir = perpendicular(positions[arm_a].mean(axis=0) - positions[edge_a].mean(axis=0))
    b_dir = perpendicular(positions[arm_b].mean(axis=0) - positions[edge_b].mean(axis=0))
    # Signed angle from arm A to arm B about the axis. A positive rotation of
    # arm A's direction swings it toward `normal`.
    phi = float(np.arctan2(axis @ np.cross(a_dir, b_dir), a_dir @ b_dir))
    normal = _unit(np.cross(axis, a_dir))
    if side is None:
        side = 1 if phi >= 0 else -1
    if side not in (1, -1):
        raise ValueError(f"side must be +1 or -1, got {side}")
    # Bring B's direction to A's turned by `side * opening` toward that side,
    # going round the way that passes over it.
    rotation = side * np.radians(opening_deg) - phi
    if side > 0 and rotation > 0:
        rotation -= 2 * np.pi
    if side < 0 and rotation < 0:
        rotation += 2 * np.pi

    # Lifting the axis by d moves every rotated point by (I - R) d, the same
    # for all of them: so the gap search only translates arm B.
    matrix = rotation_matrix(axis, rotation)
    per_nm = (np.eye(3) - matrix) @ (side * 0.5 * float(nm_to_oxdna(1.0)) * normal)
    body_a = np.setdiff1d(arm_a, np.asarray(particles.latch_a, dtype=int))
    body_b = np.setdiff1d(arm_b, np.asarray(particles.latch_b, dtype=int))
    tree = cKDTree(positions[body_a])
    turned = (positions[body_b] - pivot) @ matrix.T + pivot
    gap = GAP_START_NM
    while True:
        distances, _ = tree.query(turned + gap * per_nm)
        closest = float(oxdna_to_nm(float(distances.min())))
        if closest >= clearance_nm:
            break
        gap += GAP_STEP_NM
        if gap > GAP_MAX_NM:
            raise ValueError(
                f"no gap up to {GAP_MAX_NM} nm keeps the folded arms {clearance_nm} nm apart; "
                "the arms are too far from flat to stack"
            )

    point = pivot + side * 0.5 * float(nm_to_oxdna(gap)) * normal
    folded = rotate_particles(data, particles.arm_b, point=point, axis=axis, angle_rad=rotation)
    joint = np.asarray(particles.joint, dtype=int)
    fractions = np.asarray(particles.joint_fraction)
    for f in np.unique(fractions):
        folded = rotate_particles(
            folded, joint[fractions == f], point=point, axis=axis, angle_rad=f * rotation
        )
    new = folded[:, POSITION]
    anchors = [particles.anchor_a, particles.anchor_b]
    return HingeFold(
        data=folded,
        rotation_deg=float(np.degrees(rotation)),
        side=side,
        opening_target_deg=float(opening_deg),
        gap_nm=gap,
        closest_nm=closest,
        opening_before_deg=_opening(positions, particles),
        opening_after_deg=_opening(new, particles),
        anchor_distance_before_nm=float(
            oxdna_to_nm(np.linalg.norm(positions[anchors[0]] - positions[anchors[1]]))
        ),
        anchor_distance_after_nm=float(
            oxdna_to_nm(np.linalg.norm(new[anchors[0]] - new[anchors[1]]))
        ),
        axis_point=point,
        axis=axis,
    )


#: Opening angles and sides `best_hinge_fold` tries. Small angles only: the
#: point is a closed start, and 10 deg already puts 64 nm arms' outer edges
#: ~11 nm further apart than parallel ones.
FOLD_OPENINGS_DEG: Final = (0.0, 5.0, 10.0)
FOLD_SIDES: Final = (1, -1)


def best_hinge_fold(
    configurations: Sequence[np.ndarray],
    particles: HingeParticles,
    *,
    reach_nm: float,
    openings_deg: Sequence[float] = FOLD_OPENINGS_DEG,
    sides: Sequence[int] = FOLD_SIDES,
    clearance_nm: float = CLEARANCE_NM,
) -> tuple[int, HingeFold]:
    """The fold, over starting configurations, sides and angles, that puts the
    latch anchors within `reach_nm` with the smallest gap at the joint; when
    none does, the one whose anchors end up closest.

    Why search at all: a relaxed arm ripples by several nm, differently in
    every frame, so which frame and which face stack best is not knowable in
    advance. Why the smallest gap: the joint's single strands have to bridge
    it, and a fold that brings the anchors together by wedging the joint
    wide open starts from a joint stretched well past its contour length.
    The rule looks only at the paired bases the latch hangs from, never at
    the extensions, so the same fold serves a control that has no latch.
    Returns (index into `configurations`, fold).
    """
    best: tuple[int, HingeFold] | None = None

    def key(fold: HingeFold) -> tuple[bool, float, float]:
        within = fold.anchor_distance_after_nm <= reach_nm
        if within:
            return (False, fold.gap_nm, fold.anchor_distance_after_nm)
        return (True, fold.anchor_distance_after_nm, fold.gap_nm)

    for i, data in enumerate(configurations):
        for side in sides:
            for opening in openings_deg:
                try:
                    fold = fold_hinge(
                        data, particles, opening_deg=opening, side=side, clearance_nm=clearance_nm
                    )
                except ValueError:
                    continue
                if best is None or key(fold) < key(best[1]):
                    best = (i, fold)
    if best is None:
        raise ValueError("no configuration folds with the arms clear of each other")
    return best


def drop_particles(configuration: Configuration, remove: Sequence[int]) -> Configuration:
    """The same configuration with some particles taken out.

    How a locked-open control gets the latching hinge's exact starting shape:
    its topology is the latching one without the two extensions, in the same
    order, so removing those rows gives a configuration for it. The caller
    checks the topologies agree; this only removes rows.
    """
    keep = np.setdiff1d(np.arange(len(configuration.data)), np.asarray(remove, dtype=int))
    return Configuration(configuration.header, configuration.data[keep])

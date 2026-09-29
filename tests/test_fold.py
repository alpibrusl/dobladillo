"""Folding a hinge configuration shut, and the particle map it relies on (#17)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dobladillo import _scadnano as ad
from dobladillo.analysis.observables import hinge_opening_deg, latch_pairs_formed
from dobladillo.parts.hinge import HingeParticles, bistable_hinge
from dobladillo.sim.fold import (
    CLEARANCE_NM,
    FIELDS,
    Configuration,
    best_hinge_fold,
    drop_particles,
    fold_hinge,
    read_configuration,
    rotate_particles,
    rotation_matrix,
)
from dobladillo.units import nm_to_oxdna, oxdna_to_nm

# --- a synthetic hinge: two flat arms on a grid, in oxDNA units -------------

ROWS, COLS, SPACING = 16, 12, 1.5  # rows across the joint axis (y), columns along an arm (x)
JOINT = 4


def _synthetic(*, open_deg: float = 180.0, seed: int = 0) -> tuple[np.ndarray, HingeParticles]:
    """Arm A along -x, arm B along +x rotated so the opening is `open_deg`,
    a joint of JOINT columns between them, and one 'latch' particle per arm."""
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    arm_a: list[int] = []
    arm_b: list[int] = []
    edge_a: list[int] = []
    edge_b: list[int] = []
    joint: list[int] = []
    fraction: list[float] = []
    half = JOINT * SPACING / 2
    tilt = rotation_matrix(np.array([0.0, 1.0, 0.0]), np.radians(180.0 - open_deg))

    def add(position: np.ndarray, group: list[int]) -> int:
        a1 = np.array([0.0, 0.0, 1.0])
        a3 = np.array([1.0, 0.0, 0.0])
        rows.append(np.concatenate([position, a1, a3, rng.normal(0, 0.1, 6)]))
        group.append(len(rows) - 1)
        return len(rows) - 1

    for c in range(COLS):
        for r in range(ROWS):
            y = r * SPACING
            i = add(np.array([-half - c * SPACING, y, 0.0]), arm_a)
            if c < 2:
                edge_a.append(i)
            local = np.array([c * SPACING, y, 0.0])
            j = add(tilt @ local + np.array([half, 0.0, 0.0]), arm_b)
            if c < 2:
                edge_b.append(j)
    for k in range(JOINT):
        for r in range(ROWS):
            add(np.array([-half + (k + 0.5) * SPACING, r * SPACING, 0.0]), joint)
            fraction.append((k + 0.5) / JOINT)
    # Anchors at the outer corner of the second-to-last row of each arm, so
    # the fold's axis points along +y (toward the anchors) and arm A's
    # normal, y cross -x, is +z.
    anchor_a = arm_a[(COLS - 1) * ROWS + ROWS - 2]
    anchor_b = arm_b[(COLS - 1) * ROWS + ROWS - 2]
    particles = HingeParticles(
        arm_a=tuple(arm_a),
        arm_b=tuple(arm_b),
        edge_a=tuple(edge_a),
        edge_b=tuple(edge_b),
        joint=tuple(joint),
        joint_fraction=tuple(fraction),
        anchor_a=anchor_a,
        anchor_b=anchor_b,
        latch_a=(),
        latch_b=(),
    )
    return np.array(rows), particles


def _opening(data: np.ndarray, p: HingeParticles) -> float:
    return hinge_opening_deg(
        data[:, :3], arm_a=p.arm_a, edge_a=p.edge_a, arm_b=p.arm_b, edge_b=p.edge_b
    )


def _pairwise(points: np.ndarray) -> np.ndarray:
    return np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)


def test_rotation_is_rigid_and_turns_the_orientation_vectors_too() -> None:
    """Positions about the axis; a1, a3, v and L as vectors. A rotation that
    left a1 and a3 alone would keep every moved base pointing the old way:
    helices in place, bases unpaired."""
    data, p = _synthetic()
    moved = list(p.arm_b)
    axis = np.array([0.3, 1.0, -0.2])
    out = rotate_particles(data, moved, point=np.array([1.0, 2.0, 3.0]), axis=axis, angle_rad=1.1)

    before, after = data[moved], out[moved]
    assert np.allclose(_pairwise(before[:, :3]), _pairwise(after[:, :3]))
    r = rotation_matrix(axis, 1.1)
    for cols in (slice(3, 6), slice(6, 9), slice(9, 12), slice(12, 15)):
        assert np.allclose(after[:, cols], before[:, cols] @ r.T)
    # Orientation relative to the body is unchanged: a1 against a bond vector.
    bond_before = before[1, :3] - before[0, :3]
    bond_after = after[1, :3] - after[0, :3]
    assert np.isclose(before[0, 3:6] @ bond_before, after[0, 3:6] @ bond_after)
    untouched = np.setdiff1d(np.arange(len(data)), moved)
    assert np.array_equal(out[untouched], data[untouched])


def test_a_flat_hinge_opens_at_180_and_measures_intermediate_angles() -> None:
    for angle in (180.0, 120.0, 90.0, 30.0):
        data, p = _synthetic(open_deg=angle)
        assert _opening(data, p) == pytest.approx(angle, abs=0.5)


@pytest.mark.parametrize("target", [0.0, 10.0])
@pytest.mark.parametrize("start", [180.0, 160.0])
def test_folding_reaches_the_target_angle_and_keeps_each_arm_rigid(
    target: float, start: float
) -> None:
    data, p = _synthetic(open_deg=start)
    fold = fold_hinge(data, p, opening_deg=target, side=1)

    assert fold.opening_before_deg == pytest.approx(start, abs=0.5)
    assert fold.opening_after_deg == pytest.approx(target, abs=0.5)
    for arm in (p.arm_a, p.arm_b):
        idx = list(arm)
        assert np.allclose(_pairwise(data[idx, :3]), _pairwise(fold.data[idx, :3]))
    assert np.array_equal(fold.data[list(p.arm_a)], data[list(p.arm_a)])


def test_the_folded_arms_are_clear_of_each_other_and_stacked_on_the_chosen_side() -> None:
    data, p = _synthetic()
    for side in (1, -1):
        fold = fold_hinge(data, p, side=side)
        a = oxdna_to_nm(fold.data[list(p.arm_a), :3])
        b = oxdna_to_nm(fold.data[list(p.arm_b), :3])
        closest = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2).min()
        assert closest >= CLEARANCE_NM
        assert fold.closest_nm == pytest.approx(closest, abs=1e-6)
        # Arm A lies in z = 0 with its normal +z (axis y crossed with -x).
        height = b[:, 2].mean() - a[:, 2].mean()
        assert np.sign(height) == side
        assert abs(height) == pytest.approx(fold.gap_nm, abs=0.05)
        # The base normals of arm B were (0, 0, 1); a half turn about y flips them.
        assert np.allclose(fold.data[list(p.arm_b), 5], -1.0)


def test_folded_outer_edges_meet_and_the_joint_stays_in_chain_order() -> None:
    data, p = _synthetic()
    fold = fold_hinge(data, p, side=1)
    assert fold.anchor_distance_before_nm > 30
    assert fold.anchor_distance_after_nm == pytest.approx(fold.gap_nm, abs=0.05)
    # Each joint row turns progressively: consecutive joint particles stay
    # within one grid spacing's chord of each other.
    joint = np.array(p.joint).reshape(JOINT, ROWS)
    steps = np.linalg.norm(np.diff(fold.data[joint[:, 0], :3], axis=0), axis=1)
    assert steps.max() < 2 * SPACING + nm_to_oxdna(fold.gap_nm)


def test_a_rippled_arm_needs_a_wider_gap() -> None:
    """The real arms are not flat, and the gap is found, not assumed."""
    data, p = _synthetic()
    rippled = data.copy()
    b = list(p.arm_b)
    rippled[b, 2] += 0.8 * np.sin(rippled[b, 1])
    flat = fold_hinge(data, p, side=1)
    bumpy = fold_hinge(rippled, p, side=1)
    assert bumpy.gap_nm > flat.gap_nm
    assert bumpy.closest_nm >= CLEARANCE_NM


def test_best_fold_takes_the_smallest_gap_within_reach_else_the_closest_anchors() -> None:
    flat, p = _synthetic()
    rippled = flat.copy()
    rippled[list(p.arm_b), 2] += 0.8 * np.sin(rippled[list(p.arm_b), 1])
    candidates = [rippled, flat]
    folds = [
        fold_hinge(c, p, side=s, opening_deg=o)
        for c in candidates
        for s in (1, -1)
        for o in (0.0, 20.0)
    ]

    index, fold = best_hinge_fold(candidates, p, reach_nm=1e3, openings_deg=(0.0, 20.0))
    assert index == 1
    assert fold.gap_nm == min(f.gap_nm for f in folds)

    _, fold = best_hinge_fold(candidates, p, reach_nm=0.0, openings_deg=(0.0, 20.0))
    assert fold.opening_target_deg == 0.0
    assert fold.anchor_distance_after_nm == pytest.approx(
        min(f.anchor_distance_after_nm for f in folds), abs=1e-9
    )


def test_configuration_round_trip_and_dropping_rows(tmp_path: Path) -> None:
    data, _ = _synthetic()
    conf = Configuration(("t = 0", "b = 100.0 100.0 100.0", "E = 0 0 0"), data)
    path = tmp_path / "c.dat"
    conf.write(path)
    back = read_configuration(path)
    assert back.header == conf.header
    assert np.allclose(back.data, data)
    assert back.box.tolist() == [100.0, 100.0, 100.0]
    fewer = drop_particles(back, [0, 5])
    assert len(fewer.data) == len(data) - 2
    assert np.array_equal(fewer.data[0], data[1])
    assert fewer.data.shape[1] == FIELDS


def test_latch_pairs_count_within_the_broken_pair_distance() -> None:
    positions = np.zeros((4, 3))
    positions[1] = [1.0, 0, 0]  # paired
    positions[3] = [0, 5.0, 0]  # apart
    assert latch_pairs_formed(positions, [(0, 1), (2, 3)]) == 1
    assert latch_pairs_formed(positions, []) == 0


# --- the real hinge's particle map -------------------------------------------


@pytest.mark.parametrize("joint", [4, 32])
def test_the_particle_map_partitions_the_topology(tmp_path: Path, joint: int) -> None:
    hinge = bistable_hinge(joint_nt=joint)
    p = hinge.particles()
    files = ad.write_oxdna_files(hinge.design, directory=tmp_path, name="h")
    bases = ad.topology_bases(files["topology"])

    everything = sorted(p.arm_a + p.arm_b + p.joint)
    assert everything == list(range(len(bases)))
    assert len(p.joint) == hinge.arm_helices * joint
    assert min(p.joint_fraction) > 0 and max(p.joint_fraction) < 1
    assert set(p.edge_a) <= set(p.arm_a) and set(p.edge_b) <= set(p.arm_b)
    # The latch halves pair base for base, and hang off their anchors.
    complement = {"A": "T", "T": "A", "G": "C", "C": "G"}
    assert len(p.latch_pairs) == len(hinge.latch.sequence)  # type: ignore[union-attr]
    assert all(complement[bases[a]] == bases[b] for a, b in p.latch_pairs)
    assert p.latch_a[0] == p.anchor_a + 1 and p.latch_b[0] == p.anchor_b + 1
    assert p.anchor_a in p.arm_a and p.anchor_b in p.arm_b


def test_the_locked_open_control_is_the_latching_hinge_without_its_latch(tmp_path: Path) -> None:
    """The control starts from the latching hinge's folded configuration with
    the two extensions' rows removed. That is only right if its topology is
    exactly that: same bases, same order, extensions gone."""
    latching = bistable_hinge(joint_nt=8)
    control = bistable_hinge(joint_nt=8, latch_sequence=None)
    pl, pc = latching.particles(), control.particles()
    top_l = ad.topology_bases(
        ad.write_oxdna_files(latching.design, directory=tmp_path, name="l")["topology"]
    )
    top_c = ad.topology_bases(
        ad.write_oxdna_files(control.design, directory=tmp_path, name="c")["topology"]
    )

    removed = set(pl.latch_a + pl.latch_b)
    assert [b for i, b in enumerate(top_l) if i not in removed] == top_c
    assert pc.latch_a == pc.latch_b == ()
    assert pc.anchor_a == pl.anchor_a
    assert pc.anchor_b == pl.anchor_b - len(pl.latch_a)

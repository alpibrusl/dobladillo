"""The analysis is checked against structures whose answer is known in advance.

A measurement routine tested only on real data can be confidently wrong: the
number looks plausible and there is nothing to compare it to. So the geometry
here is synthetic and its dimensions are chosen, not measured -- a slab of
known size, a deliberately twisted sheet, a deliberately bent rod. If the code
cannot recover an answer it was handed, it cannot be trusted with one it was
not.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from dobladilo.analysis.observables import (
    analyse,
    axis_bend_nm,
    planarity_nm,
    principal_extents_nm,
    rmsf_nm,
)
from dobladilo.analysis.runs import NotAResult, check_run, load_run
from dobladilo.analysis.trajectory import Frame, read_trajectory
from dobladilo.parts.bundle import six_helix_bundle
from dobladilo.sim.jobs import write_job_bundle
from dobladilo.units import nm_to_oxdna


def _slab(nx=40, ny=20, nz=3, spacing=1.0, rng=None) -> np.ndarray:
    """A filled box: known extents of (nx-1, ny-1, nz-1) * spacing."""
    grid = np.mgrid[0:nx, 0:ny, 0:nz].reshape(3, -1).T.astype(float) * spacing
    if rng is not None:
        grid = grid + rng.normal(0, 0.01, grid.shape)
    return grid


def _frame(positions_nm: np.ndarray, step: int = 0) -> Frame:
    return Frame(
        step=step,
        box_nm=np.array([500.0, 500.0, 500.0]),
        energy=(-1.0, -1.5, 0.5),
        positions_nm=positions_nm,
        base_vectors=np.zeros_like(positions_nm),
        normals=np.zeros_like(positions_nm),
    )


# --------------------------------------------------------------- dimensions


def test_extents_recover_a_known_slab() -> None:
    extents, _ = principal_extents_nm(_slab(nx=40, ny=20, nz=3, spacing=2.0))
    # 39, 19 and 2 gaps of 2 nm. Percentile-trimmed, so allow a little slack.
    assert extents[0] == pytest.approx(78.0, abs=2.0)
    assert extents[1] == pytest.approx(38.0, abs=2.0)
    assert extents[2] == pytest.approx(4.0, abs=1.0)


def test_extents_do_not_depend_on_orientation() -> None:
    """The object has no reason to lie along the box axes, and tumbles anyway."""
    slab = _slab()
    straight, _ = principal_extents_nm(slab)

    rng = np.random.default_rng(0)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    turned, _ = principal_extents_nm(slab @ rotation)

    assert turned == pytest.approx(straight, abs=1e-6)


def test_extents_ignore_a_single_frayed_nucleotide() -> None:
    """An AFM image measures the body of an object, not one stray end."""
    slab = _slab()
    clean, _ = principal_extents_nm(slab)
    with_flyaway = np.vstack([slab, slab[0] + np.array([200.0, 0.0, 0.0])])
    frayed, _ = principal_extents_nm(with_flyaway)
    assert frayed[0] == pytest.approx(clean[0], abs=1.0)


# ------------------------------------------------------------ shape measures


def test_a_flat_sheet_is_flat_and_a_twisted_one_is_not() -> None:
    """This is the measurement the square lattice's twist correction rides on."""
    flat = _slab(nx=60, ny=20, nz=1)
    assert planarity_nm(flat) < 0.05

    # Rotate each column progressively about the long axis: a right-handed twist.
    # The angle is indexed by COLUMN, so the array has one entry per column and
    # not one per point; getting that wrong makes a sheet that is barely twisted
    # at all and the test passes for the wrong reason.
    twisted = flat.copy()
    columns = int(flat[:, 0].max()) + 1
    angle = np.linspace(0, np.pi / 3, columns)
    for i, row in enumerate(twisted):
        a = angle[int(row[0])]
        y, z = row[1] - 10.0, row[2]
        twisted[i, 1] = y * np.cos(a) - z * np.sin(a) + 10.0
        twisted[i, 2] = y * np.sin(a) + z * np.cos(a)
    assert planarity_nm(twisted) > 1.0


def test_a_straight_rod_does_not_bend_and_a_curved_one_does() -> None:
    line = np.zeros((300, 3))
    line[:, 0] = np.linspace(0, 100, 300)
    assert axis_bend_nm(line) < 0.1

    arc = line.copy()
    arc[:, 1] = 8.0 * np.sin(np.pi * line[:, 0] / 100.0)
    assert axis_bend_nm(arc) > 5.0


def test_rmsf_sees_through_tumbling() -> None:
    """A rigid object that only rotates is not fluctuating.

    Without superimposition its RMSF would be enormous, which is the whole
    reason the alignment is there.
    """
    rng = np.random.default_rng(1)
    shape = _slab(nx=20, ny=10, nz=2)
    frames = []
    for step in range(4):
        rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        if np.linalg.det(rotation) < 0:
            rotation[:, 0] *= -1
        frames.append(_frame(shape @ rotation + rng.normal(0, 5, 3), step))

    fluctuation, _ = rmsf_nm(frames)
    assert fluctuation.max() < 0.05


def test_rmsf_reports_real_motion() -> None:
    rng = np.random.default_rng(2)
    shape = _slab(nx=20, ny=10, nz=2)
    frames = [_frame(shape + rng.normal(0, 0.3, shape.shape), s) for s in range(6)]
    fluctuation, _ = rmsf_nm(frames)
    assert 0.2 < fluctuation.mean() < 0.8


def test_rmsf_needs_more_than_one_frame() -> None:
    with pytest.raises(ValueError, match="two frames"):
        rmsf_nm([_frame(_slab())])


# ------------------------------------------------------------------ parsing


def test_trajectory_round_trips_through_the_file_format(tmp_path) -> None:
    """Positions written in oxDNA units must come back as nanometres."""
    positions_nm = _slab(nx=5, ny=4, nz=2)
    raw = nm_to_oxdna(positions_nm)
    lines = ["t = 100", "b = 100 100 100", "E = -1 -1.5 0.5"]
    for row in raw:
        lines.append(" ".join(f"{v}" for v in [*row, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]))
    path = tmp_path / "traj.dat"
    path.write_text("\n".join(lines) + "\n")

    frames = read_trajectory(path)
    assert len(frames) == 1
    assert frames[0].step == 100
    assert frames[0].nucleotides == len(positions_nm)
    assert frames[0].positions_nm == pytest.approx(positions_nm, abs=1e-9)


def test_a_truncated_frame_is_rejected(tmp_path) -> None:
    """A run killed mid-write must not analyse as a short structure."""
    path = tmp_path / "traj.dat"
    path.write_text("t = 0\nb = 1 1 1\nE = 0 0 0\n1 2 3 4 5\n")
    with pytest.raises(ValueError, match="not a multiple"):
        read_trajectory(path)


def test_skipping_every_frame_is_an_error(tmp_path) -> None:
    path = tmp_path / "traj.dat"
    body = " ".join(["0"] * 15)
    path.write_text(f"t = 0\nb = 1 1 1\nE = 0 0 0\n{body}\n")
    with pytest.raises(ValueError, match="leaving none"):
        read_trajectory(path, skip=1)


# ----------------------------------------------------------------- receipts


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    directory = tmp_path_factory.mktemp("run")
    write_job_bundle(
        six_helix_bundle().design, directory=directory, name="b", part="bundle", test_mode=True
    )
    return directory


def test_a_smoke_test_is_refused_as_a_result(smoke_run) -> None:
    """The numbers from a two-thousand-step run look exactly like real ones."""
    check = check_run(smoke_run)
    assert not check.ok
    assert any("smoke test" in p for p in check.problems)
    with pytest.raises(NotAResult, match="smoke test"):
        load_run(smoke_run)


def test_an_unfinished_run_is_refused(smoke_run) -> None:
    """Stages 1 to 3 finishing says nothing about stage 4. It happened."""
    check = check_run(smoke_run, allow_test_mode=True)
    assert any("04_production produced no final configuration" in p for p in check.problems)


def test_a_trajectory_of_the_wrong_structure_is_refused(tmp_path) -> None:
    """A topology that does not match the design means the trajectory is of
    something else, however well-formed it looks."""
    write_job_bundle(
        six_helix_bundle().design, directory=tmp_path, name="b", part="bundle", test_mode=True
    )
    meta_path = tmp_path / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["nucleotides"] = 99
    meta_path.write_text(json.dumps(meta))
    assert any("not of the design it claims" in p for p in check_run(tmp_path).problems)


def test_a_directory_that_is_not_a_bundle_is_refused(tmp_path) -> None:
    assert any("not a bundle" in p for p in check_run(tmp_path).problems)


# ------------------------------------------------------------------ report


def test_plots_are_written_and_are_not_empty(tmp_path) -> None:
    """Q5 asks for plots, and the convergence one earns its place: a dimension
    still drifting at the last frame has not equilibrated, and its mean is a
    number about the journey rather than the destination. That is visible in a
    line and invisible in a mean."""
    from dobladilo.analysis.plots import write_plots

    rng = np.random.default_rng(4)
    shape = _slab(nx=25, ny=10, nz=2)
    frames = [_frame(shape + rng.normal(0, 0.15, shape.shape), s * 100) for s in range(4)]
    written = write_plots(frames, directory=tmp_path, title="synthetic")
    assert set(written) == {"structure", "convergence"}
    for path in written.values():
        assert path.stat().st_size > 5000


def test_report_carries_the_spread_not_just_the_mean() -> None:
    """An AFM histogram has a width, so the prediction needs one too."""
    rng = np.random.default_rng(3)
    shape = _slab(nx=30, ny=12, nz=2, spacing=2.0)
    frames = [_frame(shape + rng.normal(0, 0.2, shape.shape), s) for s in range(5)]
    report = analyse(frames).as_dict()
    assert report["frames"] == 5
    for axis in ("longest", "middle", "shortest"):
        assert report["dimensions_nm"][axis]["sd"] > 0
    assert report["dimensions_nm"]["longest"]["mean"] > report["dimensions_nm"]["middle"]["mean"]

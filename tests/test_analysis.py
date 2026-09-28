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

from dobladillo.analysis import _oat
from dobladillo.analysis.observables import (
    analyse,
    axis_bend_nm,
    planarity_nm,
    principal_extents_nm,
)
from dobladillo.analysis.runs import NotAResult, check_run, load_run
from dobladillo.analysis.trajectory import read_trajectory
from dobladillo.parts.bundle import six_helix_bundle
from dobladillo.sim.jobs import write_job_bundle
from dobladillo.units import OXDNA_LENGTH_UNIT_NM, nm_to_oxdna


def _slab(nx=40, ny=20, nz=3, spacing=1.0, rng=None) -> np.ndarray:
    """A filled box: known extents of (nx-1, ny-1, nz-1) * spacing."""
    grid = np.mgrid[0:nx, 0:ny, 0:nz].reshape(3, -1).T.astype(float) * spacing
    if rng is not None:
        grid = grid + rng.normal(0, 0.01, grid.shape)
    return grid


def _write_trajectory(path, positions_nm, *, rotations=None):
    """An oxDNA trajectory file of these frames, positions given in nm.

    The fluctuation is computed by oat from a FILE, so tests of it need one.
    Orientation vectors are written too, rotated with the frame when a
    rotation is given: oat averages and renormalises them, and a zero vector
    would divide by zero there.
    """
    lines = []
    for i, positions in enumerate(positions_nm):
        rotation = np.eye(3) if rotations is None else rotations[i]
        a1 = np.array([1.0, 0.0, 0.0]) @ rotation
        a3 = np.array([0.0, 0.0, 1.0]) @ rotation
        lines += [f"t = {i * 1000}", "b = 1000 1000 1000", "E = -1 -1.5 0.5"]
        for row in nm_to_oxdna(positions):
            lines.append(" ".join(f"{v:.8f}" for v in [*row, *a1, *a3, 0, 0, 0, 0, 0, 0]))
    path.write_text("\n".join(lines) + "\n")
    return path


def _analysed(tmp_path, positions_nm, *, skip=0, rotations=None):
    path = _write_trajectory(tmp_path / "traj.dat", positions_nm, rotations=rotations)
    return analyse(read_trajectory(path, skip=skip), trajectory=path, skip=skip)


def _random_rotation(rng) -> np.ndarray:
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(rotation) < 0:
        rotation[:, 0] *= -1
    return rotation


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


def test_rmsf_sees_through_tumbling(tmp_path) -> None:
    """A rigid object that only rotates is not fluctuating.

    Without superimposition its RMSF would be enormous, which is the whole
    reason the alignment is there. This is also the test that caught the
    transposed Kabsch this project once wrote; it now holds oat to it.
    """
    rng = np.random.default_rng(1)
    shape = _slab(nx=20, ny=10, nz=2)
    rotations = [_random_rotation(rng) for _ in range(4)]
    positions = [shape @ r + rng.normal(0, 5, 3) for r in rotations]
    report = _analysed(tmp_path, positions, rotations=rotations)
    assert report.rmsf_nm.max() < 0.05


def test_rmsf_reports_real_motion(tmp_path) -> None:
    rng = np.random.default_rng(2)
    shape = _slab(nx=20, ny=10, nz=2)
    positions = [shape + rng.normal(0, 0.3, shape.shape) for _ in range(6)]
    report = _analysed(tmp_path, positions)
    assert 0.2 < report.rmsf_nm.mean() < 0.8


def test_rmsf_comes_back_in_nanometres(tmp_path) -> None:
    """oat converts units inside `deviations`, with its own constant, and
    `dobladillo.units` is supposed to be the only place that happens. A flat
    sheet whose nucleotides move 0.5 nm up and down out of plane, in a
    checkerboard so nothing rotates or translates, has an RMSF of exactly
    0.5 nm -- and only if the two constants agree."""
    assert _oat.OAT_LENGTH_UNIT_NM == OXDNA_LENGTH_UNIT_NM
    sheet = _slab(nx=20, ny=10, nz=1, spacing=2.0)
    checker = np.where((sheet[:, 0] + sheet[:, 1]) / 2.0 % 2 == 0, 1.0, -1.0)
    up, down = sheet.copy(), sheet.copy()
    up[:, 2] += 0.5 * checker
    down[:, 2] -= 0.5 * checker
    report = _analysed(tmp_path, [up, down] * 3)
    assert report.rmsf_nm == pytest.approx(np.full(len(sheet), 0.5), abs=0.005)


def test_one_frame_has_no_fluctuation_and_asks_oat_nothing(tmp_path) -> None:
    report = _analysed(tmp_path, [_slab()])
    assert report.mean_structure_nm is None
    assert not report.rmsf_nm.any()
    assert report.as_dict()["rmsf_nm"]["computed_by"] is None


def test_the_rmsf_says_which_tool_computed_it(tmp_path) -> None:
    rng = np.random.default_rng(5)
    shape = _slab(nx=10, ny=5, nz=2)
    report = _analysed(tmp_path, [shape + rng.normal(0, 0.1, shape.shape) for _ in range(3)])
    assert report.as_dict()["rmsf_nm"]["computed_by"].startswith("oxDNA_analysis_tools")


def test_skipped_frames_are_skipped_by_oat_too(tmp_path) -> None:
    """Frames and fluctuation are read from the file separately. Frames 0-1
    here are wildly displaced; skip them and the fluctuation must be the
    quiet remainder's, which it is only if oat skipped the same frames."""
    rng = np.random.default_rng(6)
    shape = _slab(nx=15, ny=8, nz=2)
    noisy = [shape + rng.normal(0, 5.0, shape.shape) for _ in range(2)]
    quiet = [shape + rng.normal(0, 0.05, shape.shape) for _ in range(4)]
    report = _analysed(tmp_path, noisy + quiet, skip=2)
    assert report.frames == 4
    assert report.rmsf_nm.mean() < 0.2


def test_frames_from_another_trajectory_are_refused(tmp_path) -> None:
    """Negative control for the cross-check between the two readers."""
    rng = np.random.default_rng(8)
    shape = _slab(nx=10, ny=5, nz=2)
    path = _write_trajectory(
        tmp_path / "traj.dat", [shape + rng.normal(0, 0.1, shape.shape) for _ in range(5)]
    )
    frames = read_trajectory(path)
    with pytest.raises(ValueError, match="not the same trajectory"):
        analyse(frames[:3], trajectory=path)


def test_oat_writes_nothing_beside_the_trajectory(tmp_path) -> None:
    """oat drops a `.pyidx` index next to any trajectory it reads. Run
    directories are results and may be read-only, so it must land elsewhere."""
    rng = np.random.default_rng(9)
    shape = _slab(nx=10, ny=5, nz=2)
    run = tmp_path / "run"
    run.mkdir()
    path = _write_trajectory(
        run / "traj.dat", [shape + rng.normal(0, 0.1, shape.shape) for _ in range(3)]
    )
    _oat.deviations(path)
    assert sorted(p.name for p in run.iterdir()) == ["traj.dat"]


def test_oats_process_pool_is_put_back_after_use(tmp_path) -> None:
    """The pool is swapped for a serial loop only for the call's duration."""
    import oxDNA_analysis_tools.deviations as oat_deviations
    import oxDNA_analysis_tools.mean as oat_mean

    before = (oat_mean.oat_multiprocesser, oat_deviations.oat_multiprocesser)
    shape = _slab(nx=10, ny=5, nz=2)
    path = _write_trajectory(tmp_path / "traj.dat", [shape, shape + 0.1])
    _oat.deviations(path)
    assert (oat_mean.oat_multiprocesser, oat_deviations.oat_multiprocesser) == before
    assert before[0] is not _oat._serial


def test_superpose_undoes_a_rotation_in_the_right_direction() -> None:
    """The transposed-Kabsch regression, on oat's function: a valid rotation
    turned the wrong way still returns a rotation, so check the RESULT lands
    on the reference, not that a matrix is orthogonal."""
    rng = np.random.default_rng(10)
    shape = _slab(nx=12, ny=6, nz=3)
    reference = shape - shape.mean(axis=0)
    turned = reference @ _random_rotation(rng) + np.array([4.0, -2.0, 7.0])
    assert _oat.superpose(turned, reference) == pytest.approx(reference, abs=1e-8)


def test_superpose_does_not_fit_a_mirror_image() -> None:
    """Negative control: a reflection would superimpose a mirror image
    perfectly and report a structure as something it is not."""
    shape = _slab(nx=12, ny=6, nz=3, rng=np.random.default_rng(11))
    reference = shape - shape.mean(axis=0)
    mirrored = reference * np.array([1.0, 1.0, -1.0])
    residual = np.abs(_oat.superpose(mirrored, reference) - reference).max()
    assert residual > 0.5


def test_superpose_refuses_mismatched_structures() -> None:
    with pytest.raises(ValueError, match="same particles"):
        _oat.superpose(_slab(nx=5, ny=4, nz=2), _slab(nx=6, ny=4, nz=2))


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
    from dobladillo.analysis.plots import write_plots

    rng = np.random.default_rng(4)
    shape = _slab(nx=25, ny=10, nz=2)
    path = _write_trajectory(
        tmp_path / "traj.dat", [shape + rng.normal(0, 0.15, shape.shape) for _ in range(4)]
    )
    frames = read_trajectory(path)
    report = analyse(frames, trajectory=path)
    written = write_plots(frames, report, directory=tmp_path / "plots", title="synthetic")
    assert set(written) == {"structure", "convergence"}
    for written_path in written.values():
        assert written_path.stat().st_size > 5000


def test_report_carries_the_spread_not_just_the_mean(tmp_path) -> None:
    """An AFM histogram has a width, so the prediction needs one too."""
    rng = np.random.default_rng(3)
    shape = _slab(nx=30, ny=12, nz=2, spacing=2.0)
    report = _analysed(
        tmp_path, [shape + rng.normal(0, 0.2, shape.shape) for _ in range(5)]
    ).as_dict()
    assert report["frames"] == 5
    for axis in ("longest", "middle", "shortest"):
        assert report["dimensions_nm"][axis]["sd"] > 0
    assert report["dimensions_nm"]["longest"]["mean"] > report["dimensions_nm"]["middle"]["mean"]


def test_a_thin_trajectory_says_so(tmp_path) -> None:
    """The overnight run produced four frames because production inherited the
    relaxation checkpoint count. Nothing in the report said the numbers were
    four-sample statistics, which is how a thin result becomes a wrong one."""
    from dobladillo.analysis.observables import FRAMES_FOR_A_TRUSTWORTHY_RMSF

    rng = np.random.default_rng(7)

    def frames(n: int) -> list:
        return [_slab(nx=10, ny=5, nz=2, rng=rng) for _ in range(n)]

    (tmp_path / "thin").mkdir()
    (tmp_path / "thick").mkdir()
    thin = _analysed(tmp_path / "thin", frames(4))
    assert thin.undersampled
    assert thin.as_dict()["undersampled"] is True
    # 1/sqrt(2*3) = 0.408
    assert thin.as_dict()["rmsf_nm"]["relative_standard_error"] == pytest.approx(0.408, abs=0.001)

    thick = _analysed(tmp_path / "thick", frames(FRAMES_FOR_A_TRUSTWORTHY_RMSF))
    assert not thick.undersampled
    assert thick.as_dict()["rmsf_nm"]["relative_standard_error"] < 0.11


def test_extents_come_back_longest_first_even_when_bent() -> None:
    """SVD orders axes by variance, not by extent. For a straight object the
    two agree and the difference is invisible; for a bent one they come apart.
    The hinge at a 4 nt joint reported a "longest" of 76.6 nm and a "middle"
    of 79.4 nm -- each number right, the labels wrong."""
    # An L: a long thin arm along x, a shorter one along y, sharing a corner.
    arm_x = np.stack([np.linspace(0, 100, 400), np.zeros(400), np.zeros(400)], axis=1)
    arm_y = np.stack([np.zeros(400), np.linspace(0, 80, 400), np.zeros(400)], axis=1)
    bent = np.vstack([arm_x, arm_y]) + np.random.default_rng(0).normal(0, 0.05, (800, 3))

    extents, _ = principal_extents_nm(bent)
    assert list(extents) == sorted(extents, reverse=True)

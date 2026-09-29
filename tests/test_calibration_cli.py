"""`dobladillo calibrate` end to end: files in, a calibration with its interval out."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dobladillo.calibration.reference import load
from dobladillo.cli import app
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic_calibration import calibration_scan
from dobladillo.parts.calibration_tile import calibration_tile

runner = CliRunner()
TRUTH = {"scale_x": 1.05, "scale_y": 0.97, "skew_deg": 1.5, "anisotropy": 1.08}


def _run(*args: str) -> dict:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_reference_is_written_nominal_and_reloads(tmp_path: Path) -> None:
    out = tmp_path / "tile.json"
    payload = _run("calibrate", "reference", "--out", str(out))
    assert payload["status"] == "nominal"
    reference = load(out)
    assert not reference.traceable
    assert len(reference.features) == len(calibration_tile().features)


def test_lateral_recovers_a_known_scanner_from_scan_files(tmp_path: Path) -> None:
    tile = calibration_tile()
    scans = []
    for k in range(2):
        scan = calibration_scan(
            tile.marks_nm, sheet_nm=tile.sheet_nm, n_tiles=20, seed=70 + k, **TRUTH
        )
        scans.append(str(write_gsf(scan.image, tmp_path / f"tile-{k}.gsf")))
    payload = _run("calibrate", "lateral", *scans, "--bootstrap", "60")
    scanner = payload["scanner"]
    for key in ("scale_x", "scale_y", "skew_deg"):
        q = scanner[key]
        assert abs(q["value"] - TRUTH[key]) <= q["U_k2"], (key, q)
    assert payload["traceable"] is False
    assert payload["n_particles"] >= 10


def test_lateral_refuses_particles_that_all_land_alike(tmp_path: Path) -> None:
    tile = calibration_tile()
    scans = []
    for k in range(2):
        scan = calibration_scan(
            tile.marks_nm,
            sheet_nm=tile.sheet_nm,
            n_tiles=20,
            angles_deg=(30.0, 31.0),
            transforms=("identity",),
            seed=80 + k,
            **TRUTH,
        )
        scans.append(str(write_gsf(scan.image, tmp_path / f"tile-{k}.gsf")))
    result = runner.invoke(app, ["calibrate", "lateral", *scans, "--json"])
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "calibration_refused"


def _spike_scan(tmp_path: Path, radius_nm: float, *, featureless: bool = False) -> str:
    """Sharp spikes imaged by a known paraboloid tip, with a little noise."""
    import numpy as np

    from dobladillo.calibration.tip import dilate, paraboloid_tip
    from dobladillo.imaging.heightmap import HeightMap

    rng = np.random.default_rng(3)
    surface = np.zeros((256, 256))  # mostly substrate, as a real scan is
    if not featureless:
        for _ in range(8):
            i, j = rng.integers(20, 236, 2)
            surface[i, j] = rng.uniform(25, 40)
    image = dilate(surface, paraboloid_tip(radius_nm, 1.0, 31))
    image = image + rng.normal(0, 0.05, image.shape)
    return str(write_gsf(HeightMap(image, 1.0, "synthetic"), tmp_path / "spikes.gsf"))


def test_tip_reports_an_upper_bound_radius_and_a_resolution(tmp_path: Path) -> None:
    payload = _run("calibrate", "tip", _spike_scan(tmp_path, 10.0))
    assert payload["tip"]["informative"] is True
    radius = payload["apex_radius"]
    assert radius["determined"]
    # an outer bound: at least the true radius (within its uncertainty), not wildly above
    assert 10.0 - 2 * radius["uncertainty_nm"] <= radius["radius_nm"] <= 16.0
    assert payload["resolution"]["resolvable"]


def test_tip_says_when_the_scan_cannot_constrain_it(tmp_path: Path) -> None:
    payload = _run("calibrate", "tip", _spike_scan(tmp_path, 10.0, featureless=True))
    assert payload["tip"]["informative"] is False
    assert not payload["apex_radius"]["determined"]


def test_drift_recovers_a_known_velocity_from_frame_files(tmp_path: Path) -> None:
    import numpy as np

    from dobladillo.imaging.heightmap import HeightMap

    rng = np.random.default_rng(1)
    size, pixel, count = 128, 2.0, 80
    cx, cy = rng.uniform(-50, 300, count), rng.uniform(-50, 300, count)
    width, height = rng.uniform(5, 20, count), rng.uniform(1, 3, count)
    y, x = np.mgrid[0:size, 0:size] * pixel
    files = []
    for k in range(8):
        dx, dy = 0.3 * 10 * k, -0.2 * 10 * k  # 0.3 and -0.2 nm/s, frames 10 s apart
        frame = sum(
            height[i]
            * np.exp(-((x - dx - cx[i]) ** 2 + (y - dy - cy[i]) ** 2) / (2 * width[i] ** 2))
            for i in range(count)
        )
        frame = frame + np.random.default_rng(k).normal(0, 0.05, frame.shape)
        files.append(str(write_gsf(HeightMap(frame, pixel, "synthetic"), tmp_path / f"f{k}.gsf")))
    payload = _run("calibrate", "drift", *files, "--interval-s", "10")
    v = payload["velocity_nm_s"]
    assert abs(v["x"] - 0.3) <= max(3 * v["x_uncertainty"], 0.005)
    assert abs(v["y"] + 0.2) <= max(3 * v["y_uncertainty"], 0.005)


def test_drift_needs_exactly_one_way_of_giving_times(tmp_path: Path) -> None:
    result = runner.invoke(app, ["calibrate", "drift", "a.gsf", "b.gsf", "--json"])
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "invalid_parameters"


def test_drift_reads_one_movie_with_the_times_in_the_file(tmp_path: Path) -> None:
    """The HS-AFM route, end to end: one synthetic .asd, written in the layout
    AFMReader parses (tests/hsafm_files.py), with a drift of 3 and -2 nm/s at
    0.5 s a frame imposed. Proves consistency with AFMReader's parser, not
    that a real instrument's file is read right: there is none to test on."""
    import pytest

    pytest.importorskip("AFMReader")
    from hsafm_files import drifting_field, write_asd

    movie = tmp_path / "movie.asd"
    write_asd(movie, drifting_field(10, step_nm=(1.5, -1.0)), x_nm=256, y_nm=256, frame_time=500.0)
    payload = _run("calibrate", "drift", str(movie))
    assert payload["times_source"] == "file"
    assert payload["file_frame_interval_s"] == 0.5
    assert payload["times_s"][:3] == [0.0, 0.5, 1.0]
    assert payload["movie"] == str(movie) and payload["channel"] == "TP"
    v = payload["velocity_nm_s"]
    assert abs(v["x"] - 3.0) <= max(3 * v["x_uncertainty"], 0.02)
    assert abs(v["y"] + 2.0) <= max(3 * v["y_uncertainty"], 0.02)

    # --interval-s replaces the file's times, and says so: twice the interval, half the speed
    payload = _run("calibrate", "drift", str(movie), "--interval-s", "1.0")
    assert payload["times_source"] == "--interval-s"
    assert payload["file_frame_interval_s"] == 0.5
    assert abs(payload["velocity_nm_s"]["x"] - 1.5) <= 0.02


def test_drift_reads_an_h5jpk_movie(tmp_path: Path) -> None:
    import pytest

    pytest.importorskip("AFMReader")
    from hsafm_files import drifting_field, write_h5jpk

    movie = tmp_path / "movie.h5-jpk"
    # 128 lines a frame at 256 lines/s: 0.5 s a frame, as AFMReader computes it
    write_h5jpk(movie, drifting_field(8, step_nm=(1.5, -1.0)), pixel_nm=2.0, line_rate_hz=256.0)
    payload = _run(
        "calibrate", "drift", str(movie), "--times", ",".join(str(0.5 * k) for k in range(8))
    )
    assert payload["times_source"] == "--times"
    file_payload = _run("calibrate", "drift", str(movie))
    assert file_payload["times_source"] == "file"
    assert file_payload["times_s"] == payload["times_s"]
    # The writer stores rows the way AFMReader's flip undoes, so the drift comes
    # back as imposed. Which way up a REAL .h5-jpk is, is AFMReader's call
    # (it flips .jpk images the same way), and not checked here.
    v = file_payload["velocity_nm_s"]
    assert abs(v["y"] + 2.0) <= max(3 * v["y_uncertainty"], 0.02)
    assert abs(v["x"] - 3.0) <= max(3 * v["x_uncertainty"], 0.02)


def test_drift_refuses_a_movie_it_would_have_to_invent_times_for(tmp_path: Path) -> None:
    import pytest

    pytest.importorskip("AFMReader")
    from hsafm_files import drifting_field, write_asd

    movie = tmp_path / "movie.asd"
    write_asd(movie, drifting_field(4, step_nm=(1.0, 0.0)), x_nm=256, y_nm=256, frame_time=0.0)
    result = runner.invoke(app, ["calibrate", "drift", str(movie), "--json"])
    assert result.exit_code != 0
    error = json.loads(result.stdout)["error"]
    assert error["kind"] == "unreadable_scan"
    assert "--interval-s" in error["message"]


def test_drift_takes_one_movie_or_image_files_not_both(tmp_path: Path) -> None:
    for args in (
        ["m.asd", "f.gsf", "--interval-s", "1"],
        ["m.asd", "n.asd"],
        ["m.asd", "--interval-s", "1", "--times", "0,1"],
    ):
        result = runner.invoke(app, ["calibrate", "drift", *args, "--json"])
        assert result.exit_code != 0, args
        assert json.loads(result.stdout)["error"]["kind"] == "invalid_parameters", args

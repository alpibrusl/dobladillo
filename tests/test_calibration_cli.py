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

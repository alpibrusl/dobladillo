"""`calibrate report`: a K folder in, `post/calibration.json` out, truth recovered.

Folders are made by the real `experiment new --part calibration-tile`, so the
provenance chain is the one a person's folder has, and filled with synthetic
scans whose scanner, tip and drift were put in by hand. The refusals are
tested as carefully as the numbers: a condition the record lacks must stop
the analysis that depends on it, with a kind, and never be filled in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.experiments import check, scaffold
from dobladillo.experiments.calibration import discover
from dobladillo.experiments.instrument import CALIBRATION_CONDITIONS, angle_for, read_conditions
from dobladillo.experiments.layout import INSTRUMENT_TEMPLATE
from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.readers import write_gsf
from dobladillo.provenance import DESIGN_HASH_SCHEME, file_sha256

runner = CliRunner()
SCANNER = {"scale_x": 1.05, "scale_y": 0.97, "skew_deg": 1.5, "anisotropy": 1.08}
TIP_RADIUS_NM = 10.0
VELOCITY = (0.3, -0.2)  # nm/s
INTERVAL_S = 10.0

FILLED: dict[str, Any] = {
    "scan": {"angle_deg": 0, "direction": "trace", "closed_loop": True},
    "deposition": {"mgcl2_mm": 10, "nicl2_mm": 0},
    "tip": {"part_number": "synthetic paraboloid"},
    "frames": {"interval_s": INTERVAL_S},
}


def _new_k_folder(root: Path, slug: str = "k3") -> Path:
    result = runner.invoke(
        app,
        ["experiment", "new", slug, "--part", "calibration-tile", "--root", str(root), "--json"],
    )
    assert result.exit_code == 0, result.output
    return root / slug


def _record(directory: Path, updates: dict[str, Any]) -> None:
    path = directory / "during" / "instrument.json"
    data = json.loads(path.read_text())
    for section, values in updates.items():
        if isinstance(values, dict) and isinstance(data.get(section), dict):
            data[section].update(values)
        else:
            data[section] = values
    path.write_text(json.dumps(data, indent=2))


def _tile_scans(folder: Path, count: int = 2) -> list[Path]:
    from dobladillo.imaging.synthetic_calibration import calibration_scan
    from dobladillo.parts.calibration_tile import calibration_tile

    tile = calibration_tile()
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for k in range(count):
        scan = calibration_scan(
            tile.marks_nm, sheet_nm=tile.sheet_nm, n_tiles=20, seed=70 + k, **SCANNER
        )
        paths.append(write_gsf(scan.image, folder / f"pattern-{k + 1:02d}.gsf"))
    return paths


def _tip_scan(path: Path) -> Path:
    """Sharp spikes imaged by a known paraboloid tip: what K4's staircase is for."""
    from dobladillo.calibration.tip import dilate, paraboloid_tip

    rng = np.random.default_rng(3)
    surface = np.zeros((256, 256))
    for _ in range(8):
        i, j = rng.integers(20, 236, 2)
        surface[i, j] = rng.uniform(25, 40)
    image = dilate(surface, paraboloid_tip(TIP_RADIUS_NM, 1.0, 31))
    image = image + rng.normal(0, 0.05, image.shape)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_gsf(HeightMap(image, 1.0, "synthetic"), path)


def _frames(folder: Path, count: int = 8) -> list[Path]:
    """One field drifting at VELOCITY, a frame every INTERVAL_S."""
    rng = np.random.default_rng(1)
    size, pixel, blobs = 128, 2.0, 80
    cx, cy = rng.uniform(-50, 300, blobs), rng.uniform(-50, 300, blobs)
    width, height = rng.uniform(5, 20, blobs), rng.uniform(1, 3, blobs)
    y, x = np.mgrid[0:size, 0:size] * pixel
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for k in range(count):
        dx, dy = VELOCITY[0] * INTERVAL_S * k, VELOCITY[1] * INTERVAL_S * k
        frame = sum(
            height[i]
            * np.exp(-((x - dx - cx[i]) ** 2 + (y - dy - cy[i]) ** 2) / (2 * width[i] ** 2))
            for i in range(blobs)
        )
        frame = frame + np.random.default_rng(k).normal(0, 0.05, frame.shape)
        image = HeightMap(np.asarray(frame), pixel, "synthetic")
        paths.append(write_gsf(image, folder / f"frame-{k + 1:02d}.gsf"))
    return paths


def _report(directory: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    result = runner.invoke(app, ["calibrate", "report", str(directory), *extra, "--json"])
    return result.exit_code, json.loads(result.stdout)


# ------------------------------------------------------------ ground truth


def test_report_recovers_scanner_tip_and_drift_and_records_them(tmp_path: Path) -> None:
    directory = _new_k_folder(tmp_path)
    raw = directory / "during" / "raw"
    tiles = _tile_scans(raw / "liquid")
    tip = _tip_scan(raw / "staircase" / "S1-01.gsf")
    frames = _frames(raw / "drift")
    _record(directory, FILLED)

    code, payload = _report(directory, "--bootstrap", "40")
    assert code == 0, payload
    written = json.loads((directory / "post" / "calibration.json").read_text())
    assert written["analyses"] == payload["analyses"]

    (lateral,) = written["analyses"]["lateral"]["results"]
    assert lateral["set"] == "liquid/pattern"
    assert lateral["scans"] == ["liquid/pattern-01.gsf", "liquid/pattern-02.gsf"]
    scanner = lateral["result"]["scanner"]
    for key in ("scale_x", "scale_y", "skew_deg"):
        q = scanner[key]
        assert abs(q["value"] - SCANNER[key]) <= q["U_k2"], (key, q)
    assert lateral["result"]["traceable"] is False  # the tile is nominal until K8
    reference = written["analyses"]["lateral"]["reference"]
    assert reference["from"] == "pre/prediction.json: part"
    assert reference["design_sha256"] == written["provenance"]["design_sha256"]

    (tip_entry,) = written["analyses"]["tip"]["results"]
    assert tip_entry["block"] == "S1" and tip_entry["folder"] == "staircase"
    radius = tip_entry["result"]["apex_radius"]
    assert radius["determined"]
    # an outer bound: at least the true radius within its uncertainty, not wildly above
    assert TIP_RADIUS_NM - 2 * radius["uncertainty_nm"] <= radius["radius_nm"] <= 16.0

    (series,) = written["analyses"]["drift"]["results"]
    assert series["times_from"] == "during/instrument.json: frames.interval_s"
    v = series["result"]["velocity_nm_s"]
    assert abs(v["x"] - VELOCITY[0]) <= max(3 * v["x_uncertainty"], 0.005)
    assert abs(v["y"] - VELOCITY[1]) <= max(3 * v["y_uncertainty"], 0.005)

    # conditions, as recorded, with the record's own hash
    conditions = written["conditions"]
    assert conditions["scan"] == {
        "angle_deg": 0.0,
        "direction": "trace",
        "closed_loop": True,
        "channel": None,
    }
    assert conditions["deposition"] == {"mgcl2_mm": 10.0, "nicl2_mm": 0.0}
    assert conditions["sha256"] == file_sha256(directory / "during" / "instrument.json")

    # provenance: every scan used, by hash, tied to the design ordered
    provenance = written["provenance"]
    hashes = {s["name"]: s["sha256"] for s in provenance["scans"]}
    for path in [*tiles, tip, *frames]:
        assert hashes[str(path.relative_to(directory))] == file_sha256(path)
    assert provenance["verified"] is True
    assert written["refusals"] == []
    assert written["gate"].startswith("not evaluated")


def test_each_result_is_the_file_level_commands_payload(tmp_path: Path) -> None:
    """One shape, not two: the folder report holds what `calibrate tip` and
    `calibrate drift` print for the same files."""
    directory = _new_k_folder(tmp_path)
    raw = directory / "during" / "raw"
    tip = _tip_scan(raw / "staircase" / "S1-01.gsf")
    frames = _frames(raw, count=5)  # a series in during/raw itself: folder "."
    _record(directory, FILLED)
    code, payload = _report(directory)
    assert code == 0, payload

    single = json.loads(runner.invoke(app, ["calibrate", "tip", str(tip), "--json"]).stdout)
    assert payload["analyses"]["tip"]["results"][0]["result"] == single

    files = [str(f) for f in frames]
    drift = runner.invoke(app, ["calibrate", "drift", *files, "--interval-s", "10", "--json"])
    (series,) = payload["analyses"]["drift"]["results"]
    assert series["series"] == "."
    assert series["result"] == json.loads(drift.stdout)
    assert payload["analyses"]["lateral"]["status"] == "no_data"


# ------------------------------------------------------------ refusals


def test_an_unrecorded_condition_refuses_with_its_kind_and_writes_nothing(
    tmp_path: Path,
) -> None:
    directory = _new_k_folder(tmp_path)
    _tip_scan(directory / "during" / "raw" / "staircase" / "S1-01.gsf")
    code, payload = _report(directory)
    assert code != 0
    assert payload["error"]["kind"] == "no_scan_direction"
    assert "tip.part_number" in payload["error"]["message"]
    assert not (directory / "post" / "calibration.json").exists()


def test_a_refused_analysis_does_not_stop_the_others(tmp_path: Path) -> None:
    directory = _new_k_folder(tmp_path)
    raw = directory / "during" / "raw"
    _tip_scan(raw / "staircase" / "S1-01.gsf")
    _frames(raw / "drift", count=4)
    _record(directory, {**FILLED, "tip": {"part_number": ""}, "frames": {"interval_s": None}})
    code, payload = _report(directory)
    # every analysis with data refused: nothing to write
    assert code != 0 and payload["error"]["kind"] in ("no_tip_part_number", "no_frame_times")

    _record(directory, {"frames": {"interval_s": None, "times_s": {"drift": [0, 12, 20, 31]}}})
    code, payload = _report(directory)
    assert code == 1  # written, but not everything could be done
    assert payload["analyses"]["tip"]["status"] == "refused"
    assert payload["analyses"]["drift"]["status"] == "done"
    assert payload["analyses"]["drift"]["results"][0]["result"]["times_s"] == [0, 12, 20, 31]
    assert [r["kind"] for r in payload["refusals"]] == ["no_tip_part_number"]
    written = json.loads((directory / "post" / "calibration.json").read_text())
    assert written["refusals"] == payload["refusals"]


def test_no_scans_named_for_a_calibration_is_a_refusal(tmp_path: Path) -> None:
    directory = _new_k_folder(tmp_path)
    _record(directory, FILLED)
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "no_scans"

    # a grating, a gel and E8's control are in raw/, but none is read
    raw = directory / "during" / "raw"
    image = HeightMap(np.zeros((32, 32)), 1.0, "x")
    (raw / "grating").mkdir()
    write_gsf(image, raw / "grating" / "grating-overlap-01.gsf")
    write_gsf(image, raw / "control-01.gsf")
    (raw / "gel-A.tif").write_bytes(b"not an image")
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "no_scans"


def test_no_instrument_record_is_a_refusal(tmp_path: Path) -> None:
    directory = _new_k_folder(tmp_path)
    _tip_scan(directory / "during" / "raw" / "S1-01.gsf")
    (directory / "during" / "instrument.json").unlink()
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "no_instrument"


def test_a_movie_is_listed_not_read(tmp_path: Path) -> None:
    """The seam for a movie reader (issue #26): refused by name, not skipped."""
    directory = _new_k_folder(tmp_path)
    movie = directory / "during" / "raw" / "hsafm" / "A" / "movie-01.asd"
    movie.parent.mkdir(parents=True)
    movie.write_bytes(b"\x00" * 16)
    _record(directory, FILLED)
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "movie_not_read"


def _dummy_scans(directory: Path, *names: str) -> None:
    for name in names:
        path = directory / "during" / "raw" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"never read: the refusal comes first")


def test_lateral_refuses_a_reference_nothing_records(tmp_path: Path) -> None:
    prediction = {"part": "rectangle", "predicted_nm": {"length": 90, "width": 60}}
    directory = scaffold(tmp_path, slug="e", prediction=prediction, plan="#\n", protocol="#\n")
    _dummy_scans(directory, "pattern-01.gsf")
    _record(directory, FILLED)
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "no_calibration_reference"


def test_lateral_refuses_a_tile_that_is_not_the_predicted_design(tmp_path: Path) -> None:
    prediction = {
        "part": "calibration-tile",
        "provenance": {"design_sha256": "0" * 64, "hash_scheme": DESIGN_HASH_SCHEME},
    }
    directory = scaffold(tmp_path, slug="k", prediction=prediction, plan="#\n", protocol="#\n")
    _dummy_scans(directory, "pattern-01.gsf")
    _record(directory, FILLED)
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "design_mismatch"


def test_a_retrace_analysis_must_name_its_channel(tmp_path: Path) -> None:
    """JPK's default channel is height_trace: reading it for a record that says
    retrace would label a trace calibration as a retrace one."""
    directory = _new_k_folder(tmp_path)
    _dummy_scans(directory, "S1-01.jpk")
    _record(directory, {**FILLED, "scan": {**FILLED["scan"], "direction": "retrace"}})
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "invalid_reading"
    assert "scan.channel" in payload["error"]["message"]


def test_an_invalid_condition_is_refused_not_coerced(tmp_path: Path) -> None:
    directory = _new_k_folder(tmp_path)
    _tip_scan(directory / "during" / "raw" / "S1-01.gsf")
    _record(directory, {**FILLED, "scan": {**FILLED["scan"], "direction": "both"}})
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "invalid_reading"


# ------------------------------------------------------------ naming, record


def test_the_naming_convention(tmp_path: Path) -> None:
    prediction = {"part": "calibration-tile"}
    directory = scaffold(tmp_path, slug="k", prediction=prediction, plan="#\n", protocol="#\n")
    _dummy_scans(
        directory,
        "pattern-01.spm",
        "pattern-01.gsf",  # an export beside its native file: never both
        "pattern-02.spm",
        "liquid/overlap-01.gsf",
        "liquid/pattern-01.gsf",
        "iso/pattern-01.gsf",
        "staircase/S1-01.gsf",
        "tile/T2-03.001",
        "drift/frame-2.gsf",
        "drift/frame-10.gsf",
        "drift/frame-1.gsf",
        "grating/grating-large-01.gsf",
        "control-01.gsf",
        "gel-A.tif",
        "hsafm/A/movie-01.asd",
    )
    found = discover(directory)
    by_analysis = {
        a: {s.name: [p.name for p in s.files] for s in found.of(a)}
        for a in ("lateral", "tip", "drift")
    }
    assert by_analysis["lateral"] == {
        "pattern": ["pattern-01.spm", "pattern-02.spm"],
        "iso/pattern": ["pattern-01.gsf"],
        "liquid/overlap": ["overlap-01.gsf"],
        "liquid/pattern": ["pattern-01.gsf"],
    }
    assert by_analysis["tip"] == {
        "staircase/S1-01.gsf": ["S1-01.gsf"],
        "tile/T2-03.001": ["T2-03.001"],
    }
    assert by_analysis["drift"] == {"drift": ["frame-1.gsf", "frame-2.gsf", "frame-10.gsf"]}
    assert [m.name for m in found.movies] == ["movie-01.asd"]
    assert {s.block for s in found.of("tip")} == {"S1", "T2"}


def test_scan_angle_per_file() -> None:
    angles = {"liquid/overlap-0[12]*": 0, "liquid/overlap-*": 90}
    assert angle_for(angles, "liquid/overlap-01.spm") == 0
    assert angle_for(angles, "liquid/overlap-03.spm") == 90
    assert angle_for(angles, "air/overlap-01.spm") is None
    assert angle_for(45, "anything") == 45


def test_the_template_names_every_condition_the_protocols_need() -> None:
    conditions = read_conditions(INSTRUMENT_TEMPLATE)
    assert set(conditions.missing) == {f.name for f in CALIBRATION_CONDITIONS}
    assert INSTRUMENT_TEMPLATE["frames"]["interval_s"] is None
    filled = read_conditions({**INSTRUMENT_TEMPLATE, **FILLED})
    assert filled.missing == () and filled.invalid == ()
    blinded = read_conditions(
        {**FILLED, "deposition": {"mgcl2_mm": "blinded", "nicl2_mm": "blinded"}}
    )
    assert blinded.missing == () and blinded.get("deposition.nicl2_mm") == "blinded"
    wrong = read_conditions({**FILLED, "scan": {**FILLED["scan"], "closed_loop": "on"}})
    assert wrong.invalid == ("scan.closed_loop: not true or false: 'on'",)


@pytest.mark.parametrize("part", ["calibration-tile", "rectangle"])
def test_check_asks_for_the_conditions_only_in_calibration_folders(
    tmp_path: Path, part: str
) -> None:
    prediction = {"part": part, "predicted_nm": {"length": 90, "width": 60}}
    directory = scaffold(tmp_path, slug="x", prediction=prediction, plan="#\n", protocol="#\n")
    during = check(directory).phases[1]
    asked = [m for m in during.missing if m.startswith("instrument.json:")]
    if part == "rectangle":
        assert asked == []
        return
    assert asked == [f"instrument.json: {f.name}" for f in CALIBRATION_CONDITIONS]
    _record(directory, FILLED)
    assert not [m for m in check(directory).phases[1].missing if m.startswith("instrument.json")]
    _record(directory, {"scan": {"angle_deg": "sideways"}})
    assert check(directory).phases[1].missing[-1].startswith("instrument.json: scan.angle_deg:")


def test_lateral_fits_each_scan_angle_apart(tmp_path: Path) -> None:
    """K3's overlap scans, half at 0 and half at 90 degrees, are two calibrations:
    at 90 degrees the image's x is the scanner's other piezo. (The dummy files are
    unreadable, so each set's refusal names it: what is tested is the split.)"""
    directory = _new_k_folder(tmp_path)
    _dummy_scans(directory, *(f"liquid/overlap-0{k}.gsf" for k in range(1, 5)))
    angles = {"liquid/overlap-0[12]*": 0, "liquid/overlap-0[34]*": 90}
    _record(directory, {**FILLED, "scan": {**FILLED["scan"], "angle_deg": angles}})
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "unreadable_scan"
    assert "overlap-01" in payload["error"]["message"]
    assert "overlap-03" in payload["error"]["message"]

    _record(directory, {"scan": {"angle_deg": {"liquid/overlap-0[12]*": 0}}})
    code, payload = _report(directory)
    assert code != 0 and payload["error"]["kind"] == "no_scan_angle"
    assert "liquid/overlap-03.gsf" in payload["error"]["message"]

"""The blinded E2 comparison script that students run."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic import synthetic_scan

SCRIPT = Path(__file__).resolve().parent.parent / "experiments" / "protocols" / "e2_compare.py"


def _load():
    spec = importlib.util.spec_from_file_location("e2_compare", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arm(tmp: Path, name: str, flat: int, twisted: int, scans: int, seed: int) -> list[Path]:
    paths = []
    for i in range(scans):
        scan = synthetic_scan(
            seed=seed + i,
            n_rectangles=flat,
            n_twisted=twisted,
            n_aggregates=2,
            length_nm=191.2,
            width_nm=36.0,
            bow_nm=4.0,
            drift_shear=0.05,
            streak_lines=12,
        )
        paths.append(write_gsf(scan.image, tmp / f"{name}-{i}.gsf"))
    return paths


def test_the_script_recovers_a_real_difference_and_stays_blind(tmp_path: Path) -> None:
    """The analyst knows the samples only as X and Y, so the script must never
    need to know which is corrected -- it states the verdict both ways."""
    x = _arm(tmp_path, "X", 34, 2, 3, seed=0)
    y = _arm(tmp_path, "Y", 6, 30, 3, seed=10)
    out = tmp_path / "arms.json"
    code = _load().main(
        [
            "--x",
            *map(str, x),
            "--tip-x",
            "10",
            "--y",
            *map(str, y),
            "--tip-y",
            "10",
            "--reference-height",
            "2.0",
            "--out",
            str(out),
        ]
    )
    result = json.loads(out.read_text())
    assert code == 0
    assert result["X"]["total"] >= 100 and result["Y"]["total"] >= 100
    assert result["verdict_if_x_is_corrected"] == "correction helps"
    assert result["verdict_if_y_is_corrected"] == "correction hurts"
    assert result["too_few_particles"] == []


def test_too_few_particles_is_flagged_and_fails(tmp_path: Path) -> None:
    """The gate requires 100 per arm; one scan gives about 36. A run that falls
    short must say so and exit non-zero rather than report a confident verdict
    from an interval too wide to mean anything."""
    x = _arm(tmp_path, "X", 34, 2, 1, seed=0)
    y = _arm(tmp_path, "Y", 6, 30, 1, seed=10)
    out = tmp_path / "arms.json"
    code = _load().main(
        [
            "--x",
            *map(str, x),
            "--tip-x",
            "10",
            "--y",
            *map(str, y),
            "--tip-y",
            "10",
            "--reference-height",
            "2.0",
            "--out",
            str(out),
        ]
    )
    assert code == 1
    assert set(json.loads(out.read_text())["too_few_particles"]) == {"X", "Y"}


def test_the_tip_radius_and_reference_height_are_required() -> None:
    """Same rule as everywhere else: no defaults for measured quantities."""
    with pytest.raises(SystemExit):
        _load().main(["--x", "a.gsf", "--y", "b.gsf", "--reference-height", "2.0"])
    with pytest.raises(SystemExit):
        _load().main(["--x", "a.gsf", "--y", "b.gsf", "--tip-x", "10", "--tip-y", "10"])

"""`dobladillo experiment compare-arms`: E2's blinded two-arm readout.

These were the tests of `experiments/protocols/e2_compare.py`, which this
command replaced. The behaviour they pin is the same -- 100 particles per arm,
Newcombe interval, classification against the arm plus the tip, the verdict
stated under both unblindings -- and so is the rule they started with: no
defaults for measured quantities. What changed is where those come from: the
folder's record, not flags a person or an agent could fill with a guess.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.experiments import scaffold
from dobladillo.experiments.arms import RecordIncomplete, read_record
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic import synthetic_scan

PREDICTION = {
    "part": "twist-corrected",
    "predicted_nm": {"length": 191.2, "width": 36.0, "height": 2.0},
}


def _folder(tmp: Path, **instrument: Any) -> Path:
    """An E2 folder with a complete session record, unless told otherwise."""
    directory = scaffold(tmp, slug="e2", prediction=PREDICTION, plan="# p\n", protocol="# p\n")
    record = json.loads((directory / "during" / "instrument.json").read_text())
    record["tip"]["measured_radius_before_nm"] = 10.0
    record["tip"]["measured_radius_between_nm"] = 10.0
    record["tip"]["measured_radius_after_nm"] = 10.0
    record["imaging_order"] = ["X", "Y"]
    record["reference"] = {"flat_height_nm": 2.0, "from": "E1 post/measurements.json"}
    for key, value in instrument.items():
        if key.startswith("tip."):
            record["tip"][key[4:]] = value
        else:
            record[key] = value
    (directory / "during" / "instrument.json").write_text(json.dumps(record))
    return directory


def _arm(directory: Path, name: str, flat: int, twisted: int, scans: int, seed: int) -> None:
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
        write_gsf(scan.image, directory / "during" / "raw" / f"{name}-{i + 1:02d}.gsf")


def _run(directory: Path) -> Any:
    return CliRunner().invoke(app, ["experiment", "compare-arms", str(directory), "--json"])


def test_the_command_recovers_a_real_difference_and_stays_blind(tmp_path: Path) -> None:
    """The analyst knows the samples only as X and Y, so the command must never
    need to know which is corrected -- it states the verdict both ways."""
    directory = _folder(tmp_path)
    _arm(directory, "X", 34, 2, 3, seed=0)
    _arm(directory, "Y", 6, 30, 3, seed=10)
    run = _run(directory)
    assert run.exit_code == 0, run.output
    result = json.loads((directory / "post" / "arms.json").read_text())
    assert result["X"]["total"] >= 100 and result["Y"]["total"] >= 100
    assert result["verdict_if_x_is_corrected"] == "correction helps"
    assert result["verdict_if_y_is_corrected"] == "correction hurts"
    assert result["too_few_particles"] == []
    low, high = result["ci95"]
    assert low > 0, "a 70-point difference at 100 per arm should exclude zero"
    assert json.loads(run.stdout)["difference_x_minus_y"] == result["difference_x_minus_y"]
    assert len(result["X"]["scans"]) == 3 and all("X-" in s for s in result["X"]["scans"])


def test_too_few_particles_is_flagged_and_fails(tmp_path: Path) -> None:
    """The gate requires 100 per arm; one scan gives about 36. A run that falls
    short must say so and exit non-zero rather than report a confident verdict
    from an interval too wide to mean anything."""
    directory = _folder(tmp_path)
    _arm(directory, "X", 34, 2, 1, seed=0)
    _arm(directory, "Y", 6, 30, 1, seed=10)
    run = _run(directory)
    assert run.exit_code == 1
    assert set(json.loads((directory / "post" / "arms.json").read_text())["too_few_particles"]) == {
        "X",
        "Y",
    }


def _refusal(directory: Path) -> dict[str, Any]:
    """Refusals happen before any scan is read, so no scans are needed."""
    run = _run(directory)
    assert run.exit_code != 0
    assert not (directory / "post" / "arms.json").exists(), "refused, yet wrote a result"
    return dict(json.loads(run.stdout)["error"])


@pytest.mark.parametrize(
    "missing",
    ["measured_radius_before_nm", "measured_radius_between_nm", "measured_radius_after_nm"],
)
def test_every_tip_reading_is_required(tmp_path: Path, missing: str) -> None:
    """Same rule as everywhere else: no defaults for measured quantities. A
    missing between-sample reading is not replaced by the mean of the other
    two, and a nominal radius on the box is not read at all."""
    directory = _folder(tmp_path, **{f"tip.{missing}": None, "tip.nominal_radius_nm": 10.0})
    error = _refusal(directory)
    assert error["kind"] == "no_tip_radius"
    assert missing in error["message"]
    assert "nominal" in error["message"]


def test_the_reference_height_is_required(tmp_path: Path) -> None:
    """Not the model's 2.0 nm: dry imaging compresses everything."""
    directory = _folder(tmp_path, reference={"flat_height_nm": None, "from": ""})
    error = _refusal(directory)
    assert error["kind"] == "no_reference_height"


def test_the_imaging_order_is_required(tmp_path: Path) -> None:
    """It decides which tip readings bracket which arm, and it was a coin flip."""
    directory = _folder(tmp_path, imaging_order=None)
    assert _refusal(directory)["kind"] == "no_imaging_order"
    directory = _folder(tmp_path / "b", imaging_order=["X", "X"])
    assert _refusal(directory)["kind"] == "no_imaging_order"


def test_a_missing_prediction_is_refused(tmp_path: Path) -> None:
    directory = _folder(tmp_path)
    (directory / "pre" / "prediction.json").unlink()
    assert _refusal(directory)["kind"] == "no_prediction"


def test_missing_scans_of_one_arm_are_refused(tmp_path: Path) -> None:
    directory = _folder(tmp_path)
    _arm(directory, "X", 4, 0, 1, seed=0)
    error = _refusal(directory)
    assert error["kind"] == "no_scans"
    assert "Y-" in error["message"]


def test_each_arm_gets_the_tip_readings_that_bracket_it(tmp_path: Path) -> None:
    """A tip that blunts between the samples images them with different tips.
    The arm imaged first takes the mean of before and between; the second,
    between and after -- whichever label the coin put first."""
    directory = _folder(
        tmp_path,
        imaging_order=["Y", "X"],
        **{
            "tip.measured_radius_before_nm": 10.0,
            "tip.measured_radius_between_nm": 12.0,
            "tip.measured_radius_after_nm": 16.0,
        },
    )
    record = read_record(directory)
    assert record.tip_radius["Y"].value == pytest.approx(11.0)
    assert record.tip_radius["X"].value == pytest.approx(14.0)
    # The spread across the bracketing readings is carried, not averaged away.
    assert record.tip_radius["X"].uncertainty == pytest.approx(4.0)
    assert "between_nm and _after_nm" in record.tip_radius["X"].source
    # Negative control: the other order gives the other assignment, so the
    # test above is sensitive to the order rather than passing by symmetry.
    other = _folder(
        tmp_path / "b",
        imaging_order=["X", "Y"],
        **{
            "tip.measured_radius_before_nm": 10.0,
            "tip.measured_radius_between_nm": 12.0,
            "tip.measured_radius_after_nm": 16.0,
        },
    )
    assert read_record(other).tip_radius["X"].value == pytest.approx(11.0)


def test_a_non_positive_tip_reading_is_refused(tmp_path: Path) -> None:
    directory = _folder(tmp_path, **{"tip.measured_radius_between_nm": 0})
    with pytest.raises(RecordIncomplete) as caught:
        read_record(directory)
    assert caught.value.kind == "invalid_reading"


def test_the_command_cannot_be_told_which_arm_is_corrected() -> None:
    """Blinding is enforced by the interface, not by good intentions: there is
    no option through which the key could be passed, even by mistake."""
    run = CliRunner().invoke(app, ["describe", "--json"])
    commands = {c["command"]: c for c in json.loads(run.stdout)["commands"]}
    options = commands["experiment compare-arms"]["options"]
    flags = " ".join(flag for option in options for flag in option["flags"])
    assert "corrected" not in flags
    assert "tip" not in flags and "reference" not in flags, "measured values come from the record"

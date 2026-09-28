"""The experiment layout, and the ordering check that is the point of it."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dobladillo.experiments import PHASES, REQUIRED, check, recorded_at, scaffold

PREDICTION = {"part": "rectangle", "predicted_nm": {"length": 106.2, "width": 66.0}}


def _make(root: Path, slug: str = "x") -> Path:
    return scaffold(root, slug=slug, prediction=PREDICTION, plan="# plan\n", protocol="# p\n")


def _git(directory: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def test_scaffold_makes_all_three_phases(tmp_path: Path) -> None:
    directory = _make(tmp_path)
    for phase in PHASES:
        assert (directory / phase).is_dir()
        assert (directory / phase / "README.md").is_file()


def test_scaffold_refuses_to_overwrite(tmp_path: Path) -> None:
    _make(tmp_path)
    with pytest.raises(FileExistsError, match="already exists"):
        _make(tmp_path)


def test_a_fresh_experiment_is_ready_for_during(tmp_path: Path) -> None:
    """`pre` is complete on creation except for the order files, which the CLI
    writes; the layout itself only owns the documents."""
    directory = _make(tmp_path)
    (directory / "pre" / "order" / "bulk.csv").write_text("name,sequence\n")
    report = check(directory)
    assert report.phases[0].complete
    assert report.ready_for == "during"


def test_every_required_file_is_reported_when_missing(tmp_path: Path) -> None:
    directory = tmp_path / "empty"
    (directory / "pre").mkdir(parents=True)
    report = check(directory)
    assert set(report.phases[0].missing) == set(REQUIRED["pre"])


def test_no_prediction_is_a_problem_not_a_gap(tmp_path: Path) -> None:
    """A missing plan is incompleteness. A missing prediction means there is
    nothing the experiment could fail against."""
    directory = _make(tmp_path)
    (directory / "pre" / "prediction.json").unlink()
    report = check(directory)
    assert any("nothing was predicted" in p for p in report.problems)
    assert not report.results_believable


def test_an_uncommitted_folder_says_its_timestamps_are_not_evidence(tmp_path: Path) -> None:
    """A clone resets every mtime to the moment of checkout, so a filesystem
    time proves nothing about when a prediction was made."""
    directory = _make(tmp_path)
    (directory / "during" / "raw" / "scan.gsf").write_text("x")
    report = check(directory)
    assert any("comes from the filesystem" in p for p in report.problems)


def test_a_prediction_committed_before_the_data_is_clean(repo: Path) -> None:
    """Clean means the whole record, so this folder carries the provenance
    chain `experiment new` writes; without it the design check fires, as
    tests/test_provenance.py shows."""
    from dobladillo.provenance import design_record, write_order_manifest

    design = "a" * 64
    prediction = {**PREDICTION, "provenance": design_record(design, part="rectangle")}
    directory = scaffold(repo, slug="x", prediction=prediction, plan="# p\n", protocol="# p\n")
    order = directory / "pre" / "order"
    (order / "bulk.csv").write_text("name,sequence\n")
    write_order_manifest(
        order, name="rectangle", part="rectangle", design_hash=design, files=[order / "bulk.csv"]
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pre-register")

    import time

    time.sleep(1.1)
    (directory / "during" / "raw" / "scan.gsf").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "raw")

    report = check(directory)
    assert report.problems == ()
    assert report.results_believable
    assert report.prediction is not None
    assert report.prediction.trustworthy


def test_a_prediction_amended_after_the_data_is_caught(repo: Path) -> None:
    """The failure the whole layout exists to make visible. The comparison
    would look identical either way."""
    import time

    directory = _make(repo)
    (directory / "pre" / "order" / "bulk.csv").write_text("name,sequence\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pre-register")

    time.sleep(1.1)
    (directory / "during" / "raw" / "scan.gsf").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "raw")

    time.sleep(1.1)
    (directory / "pre" / "prediction.json").write_text(
        json.dumps({"predicted_nm": {"length": 999}})
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "amend")

    report = check(directory)
    assert any("recorded AFTER the first raw file" in p for p in report.problems)
    assert not report.results_believable


def test_a_same_second_tie_is_reported_rather_than_passed(repo: Path) -> None:
    """Git commit times have one-second granularity. A tie cannot happen
    across a real experiment and happens easily in a script, which is exactly
    when silence would be wrong."""
    directory = _make(repo)
    (directory / "pre" / "order" / "bulk.csv").write_text("name,sequence\n")
    (directory / "during" / "raw" / "scan.gsf").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "everything at once")

    report = check(directory)
    assert any("same timestamp" in p for p in report.problems)


def test_the_raw_readme_does_not_count_as_data(tmp_path: Path) -> None:
    """Otherwise the folder scaffolds itself into looking like it has data,
    and the ordering check compares the prediction against a template."""
    directory = _make(tmp_path)
    assert (directory / "during" / "raw" / "README.md").is_file()
    report = check(directory)
    assert "raw/" in report.phases[1].missing


def test_recorded_at_reports_a_missing_file_as_missing(tmp_path: Path) -> None:
    assert recorded_at(tmp_path / "nope.json").source == "missing"


# ------------------------------------------------------- refusing to guess


def _cli(*args: str):
    from typer.testing import CliRunner

    from dobladillo.cli import app

    return CliRunner().invoke(app, list(args))


def test_compare_will_not_default_the_tip_radius() -> None:
    """A default here is a landmine: the command runs, the answer is plausible,
    and the width is a quarter wrong. Required, so it cannot be skipped by an
    assistant trying to make a command succeed."""
    result = _cli("compare", "rectangle")
    assert result.exit_code != 0
    assert "tip-radius" in result.output or "tip_radius" in result.output


def test_report_refuses_without_a_measured_tip_radius(tmp_path: Path) -> None:
    directory = _make(tmp_path)
    (directory / "pre" / "order" / "b.csv").write_text("x\n")
    (directory / "during" / "raw" / "s.gsf").write_text("not really")
    result = _cli("experiment", "report", str(directory))
    assert result.exit_code != 0
    assert "no measured tip radius" in result.output
    assert "nominal" in result.output


def test_report_refuses_without_a_prediction(tmp_path: Path) -> None:
    """There is nothing the experiment could be compared against, and it
    cannot be written now -- that is the whole point of pre-registration."""
    directory = _make(tmp_path)
    (directory / "pre" / "prediction.json").unlink()
    result = _cli("experiment", "report", str(directory))
    assert result.exit_code != 0
    assert "nothing this experiment could be" in result.output


def test_the_agent_guide_names_the_field_most_likely_to_be_guessed() -> None:
    """A rule nobody reads is not a control. This one has to be specific
    enough to recognise in the moment."""
    guide = Path(__file__).resolve().parent.parent / "experiments" / "AGENTS.md"
    text = guide.read_text()
    assert "tip radius" in text
    assert "Never write a number" in text
    assert "experiment report" in text


def test_report_counts_every_scan_and_classifies_against_the_image(tmp_path: Path) -> None:
    """Two bugs a student following E1 would have hit, pinned together.

    `experiment report` insisted on exactly one .gsf, while E1 asks for 300
    particles and one overview holds about 40. And it classified particles
    against the OBJECT's dimensions while the image shows object plus tip, so a
    good sample read as nearly all malformed -- the bug `afm measure` had and
    lost, surviving here.
    """
    import json as _json

    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan
    from dobladillo.parts.twist_pair import twist_pair

    part = twist_pair().corrected.as_dict()
    dims = sorted(part["approx_dimensions_nm"].values(), reverse=True)
    prediction = {
        "part": "twist-corrected",
        "predicted_nm": {"length": dims[0], "width": dims[-1], "height": 2.0},
    }
    directory = scaffold(tmp_path, slug="x", prediction=prediction, plan="# p\n", protocol="# p\n")
    for i in range(3):
        scan = synthetic_scan(seed=i, length_nm=dims[0], width_nm=dims[-1], n_aggregates=0)
        write_gsf(scan.image, directory / "during" / "raw" / f"scan-{i}.gsf")
    instrument = _json.loads((directory / "during" / "instrument.json").read_text())
    instrument["tip"]["measured_radius_before_nm"] = 10.0
    instrument["tip"]["measured_radius_after_nm"] = 10.0
    (directory / "during" / "instrument.json").write_text(_json.dumps(instrument))

    result = _cli("experiment", "report", str(directory), "--json")
    assert result.exit_code == 0, result.output
    measured = _json.loads((directory / "post" / "measurements.json").read_text())
    assert len(measured["scans"]) == 3, "only one scan was analysed"
    assert measured["particles"] > 100
    # The radius used is written down with where it came from, so a result
    # can always be traced back to the reading it rests on.
    assert measured["tip_radius"]["kind"] == "measured"
    assert "measured_radius_before_nm" in measured["tip_radius"]["source"]
    assert measured["population"]["well_formed"]["fraction"] > 0.9, (
        "a clean synthetic sample did not read as well formed"
    )


def test_report_reads_native_files_and_not_the_exports_beside_them(tmp_path: Path) -> None:
    """The protocols used to ask for a .gsf next to every native file. Native
    files are read directly now, so a folder following the old protocol holds
    every image twice, and reading both would double every count. Native wins,
    the exports are named as skipped, and nothing is counted twice."""
    import json as _json
    import shutil

    pytest.importorskip("AFMReader")
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan

    prediction = {"part": "rectangle", "predicted_nm": {"length": 90, "width": 60, "height": 2}}
    directory = scaffold(tmp_path, slug="x", prediction=prediction, plan="# p\n", protocol="# p\n")
    raw = directory / "during" / "raw"
    native = Path(__file__).resolve().parent / "data" / "afm_native" / "sample_0.stp"
    shutil.copy(native, raw / "scan-01.stp")
    write_gsf(synthetic_scan(seed=1).image, raw / "scan-01.gsf")
    instrument = _json.loads((directory / "during" / "instrument.json").read_text())
    instrument["tip"]["measured_radius_before_nm"] = 10.0
    (directory / "during" / "instrument.json").write_text(_json.dumps(instrument))

    result = _cli("experiment", "report", str(directory), "--json")
    assert result.exit_code == 0, result.output
    measured = _json.loads((directory / "post" / "measurements.json").read_text())
    assert [Path(s).name for s in measured["scans"]] == ["scan-01.stp"]
    assert "not the 1 .gsf exports" in result.stderr

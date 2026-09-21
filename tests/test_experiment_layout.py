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
    directory = _make(repo)
    (directory / "pre" / "order" / "bulk.csv").write_text("name,sequence\n")
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

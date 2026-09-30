"""The experimentalist's acts at the CLI: gate, lock, log, record, upload, commit.

Each is a human act that writes the record, so what matters most is what each
refuses: a gate after the lock, raw data before it, a raw file over another,
a reading that cannot be one, a path out of the folder, a folder outside git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.experiments import check, scaffold
from dobladillo.experiments.layout import INSTRUMENT_TEMPLATE
from dobladillo.experiments.lifecycle import _fields, template_fields
from dobladillo.provenance import file_sha256

PREDICTION = {"part": "rectangle", "predicted_nm": {"length": 106.2, "width": 66.0}}
PLAN = "# e\n\n## The gate\n\n> criterion:\n\n## What is predicted\n\nstuff\n"


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=directory, check=True, capture_output=True, text=True
    ).stdout


def _run(*args: str) -> tuple[int, dict]:
    result = CliRunner().invoke(app, [*args, "--json"])
    return result.exit_code, json.loads(result.stdout)


def _folder(root: Path, slug: str = "e1") -> Path:
    directory = scaffold(root, slug=slug, prediction=PREDICTION, plan=PLAN, protocol="# p\n")
    (directory / "pre" / "order" / "bulk.csv").write_text("name,sequence\n")
    return directory


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "bench@example.invalid")
    _git(tmp_path, "config", "user.name", "Bench Person")
    return tmp_path


@pytest.fixture
def folder(repo: Path) -> Path:
    return _folder(repo / "experiments")


@pytest.fixture
def locked(folder: Path) -> Path:
    assert _run("experiment", "criterion", str(folder), "fails if width is off by 10%")[0] == 0
    code, out = _run("experiment", "lock", str(folder))
    assert code == 0, out
    return folder


def _kind(out: dict) -> str:
    return out["error"]["kind"]


# ------------------------------------------------------------------ gate


def test_the_criterion_is_written_into_the_plan_and_check_stops_asking(folder: Path) -> None:
    assert any("gate is not written" in p for p in check(folder).problems)
    code, out = _run("experiment", "criterion", str(folder), "width off by more than 10%")
    assert code == 0, out
    assert "> criterion: width off by more than 10%" in (folder / "pre" / "plan.md").read_text()
    assert out["criterion"] == "width off by more than 10%"
    assert not any("gate is not written" in p for p in check(folder).problems)


def test_a_multi_line_criterion_round_trips_and_can_be_rewritten(folder: Path) -> None:
    _run("experiment", "criterion", str(folder), "first\n\nsecond line")
    code, out = _run("experiment", "criterion", str(folder), "replaced")
    assert code == 0 and out["previous"] == "first\n\nsecond line"
    plan = (folder / "pre" / "plan.md").read_text()
    assert "> criterion: replaced\n\n## What is predicted" in plan
    assert "second line" not in plan


def test_an_empty_criterion_is_refused(folder: Path) -> None:
    code, out = _run("experiment", "criterion", str(folder), "   \n ")
    assert code == 1 and _kind(out) == "empty_criterion"


def test_the_criterion_is_refused_once_pre_is_locked(locked: Path) -> None:
    before = (locked / "pre" / "plan.md").read_text()
    code, out = _run("experiment", "criterion", str(locked), "a new gate, after the fact")
    assert code == 1 and _kind(out) == "locked"
    assert (locked / "pre" / "plan.md").read_text() == before


def test_a_plan_without_a_criterion_line_is_refused(folder: Path) -> None:
    (folder / "pre" / "plan.md").write_text("# no gate line\n")
    assert _kind(_run("experiment", "criterion", str(folder), "x")[1]) == "no_gate_line"


# ------------------------------------------------------------------ lock


def test_lock_commits_pre_with_the_local_identity(folder: Path) -> None:
    _run("experiment", "criterion", str(folder), "fails if width is off by 10%")
    code, out = _run("experiment", "lock", str(folder))
    assert code == 0, out
    assert out["commit"]["sha"] == _git(folder, "rev-parse", "HEAD").strip()
    assert out["commit"]["author"] == "Bench Person <bench@example.invalid>"
    assert all("/pre/" in f for f in out["files"])
    assert not _git(folder, "status", "--porcelain", "--", "pre").strip()
    status = _run("experiment", "status", str(folder))[1]
    assert status["lock"]["locked"] and status["lock"]["committed_gate"].startswith("fails")


def test_lock_refuses_without_a_gate(folder: Path) -> None:
    code, out = _run("experiment", "lock", str(folder))
    assert code == 1 and _kind(out) == "no_criterion"
    no_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=folder, capture_output=True)
    assert no_commit.returncode != 0


def test_lock_refuses_an_incomplete_pre(folder: Path) -> None:
    _run("experiment", "criterion", str(folder), "x")
    (folder / "pre" / "order" / "bulk.csv").unlink()
    code, out = _run("experiment", "lock", str(folder))
    assert code == 1 and _kind(out) == "pre_incomplete" and "order/" in out["error"]["message"]


def test_lock_refuses_outside_git(tmp_path: Path) -> None:
    directory = _folder(tmp_path)
    _run("experiment", "criterion", str(directory), "x")
    code, out = _run("experiment", "lock", str(directory))
    assert code == 1 and _kind(out) == "not_in_git"


def test_lock_refuses_when_pre_is_committed_and_unchanged(locked: Path) -> None:
    code, out = _run("experiment", "lock", str(locked))
    assert code == 1 and _kind(out) == "already_locked"


def test_a_gate_in_the_working_copy_is_not_a_lock(folder: Path) -> None:
    """Committing pre/ with an empty gate, then writing one, is not locked:
    the lock is read from the commit."""
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "scaffold")
    _run("experiment", "criterion", str(folder), "written after the scaffold commit")
    assert not _run("experiment", "status", str(folder))[1]["lock"]["locked"]
    assert _run("experiment", "lock", str(folder))[0] == 0


# ------------------------------------------------------------------ log


def test_log_appends_a_timestamped_entry(folder: Path) -> None:
    before = (folder / "during" / "log.md").read_text()
    code, out = _run("experiment", "log", str(folder), "Used the older buffer")
    assert code == 0, out
    after = (folder / "during" / "log.md").read_text()
    assert after.startswith(before)
    assert f"### {out['at']} — Bench Person\n\nUsed the older buffer\n" in after
    assert _kind(_run("experiment", "log", str(folder), "  ")[1]) == "empty_entry"


# ------------------------------------------------------------------ record


def test_every_template_field_can_be_recorded_and_nothing_else() -> None:
    """A field added to INSTRUMENT_TEMPLATE without a way to record it, or a
    recordable field the template lacks, fails here."""
    assert {".".join(p) for p in template_fields()} == {f.name for f in _fields()}


def test_record_sets_typed_values(folder: Path) -> None:
    code, out = _run(
        "experiment",
        "record",
        str(folder),
        "--set",
        "tip.measured_radius_before_nm=9.5",
        "--set",
        "scan.pixels=512",
        "--set",
        "scan.direction=trace",
        "--set",
        "scan.closed_loop=true",
        "--set",
        "deposition.nicl2_mm=blinded",
        "--set",
        'scan.angle_deg={"liquid/overlap-0[12]*": 0, "liquid/overlap-0[34]*": 90}',
        "--set",
        "imaging_order=Y,X",
        "--set",
        'frames.times_s={"liquid": [0, 64, 128]}',
        "--set",
        "instrument=Bruker Dimension Icon",
    )
    assert code == 0, out
    data = json.loads((folder / "during" / "instrument.json").read_text())
    assert data["tip"]["measured_radius_before_nm"] == 9.5
    assert data["scan"]["pixels"] == 512 and data["scan"]["closed_loop"] is True
    assert data["deposition"]["nicl2_mm"] == "blinded"
    assert data["scan"]["angle_deg"]["liquid/overlap-0[34]*"] == 90
    assert data["imaging_order"] == ["Y", "X"]
    assert data["frames"]["times_s"] == {"liquid": [0, 64, 128]}
    assert data["tip"]["note"] == INSTRUMENT_TEMPLATE["tip"]["note"]
    # Read back as the analyses read it: a Measured tip radius.
    from dobladillo.experiments.instrument import read_instrument

    record = read_instrument(folder)
    assert record is not None and record.tip["before"] is not None
    assert record.tip["before"].value == 9.5


def test_an_empty_value_clears_a_field(folder: Path) -> None:
    _run("experiment", "record", str(folder), "--set", "tip.measured_radius_before_nm=9.5")
    _run("experiment", "record", str(folder), "--set", "tip.measured_radius_before_nm=")
    data = json.loads((folder / "during" / "instrument.json").read_text())
    assert data["tip"]["measured_radius_before_nm"] is None


@pytest.mark.parametrize(
    ("assignment", "kind"),
    [
        ("tip.bogus=1", "unknown_field"),
        ("tip.note=anything", "unknown_field"),
        ("tip.measured_radius_before_nm=0", "invalid_value"),
        ("tip.measured_radius_before_nm=ten", "invalid_value"),
        ("tip.measured_radius_before_nm=nan", "invalid_value"),
        ("scan.direction=sideways", "invalid_value"),
        ("scan.closed_loop=yes", "invalid_value"),
        ("scan.pixels=1.5", "invalid_value"),
        ("deposition.mgcl2_mm=-1", "invalid_value"),
        ("buffer.ph=15", "invalid_value"),
        ("imaging_order=X,X", "invalid_value"),
        ('scan.angle_deg={"a": "b"}', "invalid_value"),
        ("no-equals-sign", "invalid_parameters"),
    ],
)
def test_record_refuses_what_cannot_be_a_reading(folder: Path, assignment: str, kind: str) -> None:
    path = folder / "during" / "instrument.json"
    before = path.read_text()
    # A good assignment first: a refusal must leave even that unwritten.
    code, out = _run(
        "experiment",
        "record",
        str(folder),
        "--set",
        "temperature_c=21",
        "--set",
        assignment,
    )
    assert code == 1 and _kind(out) == kind, out
    assert path.read_text() == before


def test_record_without_set_lists_fields_and_writes_nothing(folder: Path) -> None:
    path = folder / "during" / "instrument.json"
    before = path.read_text()
    code, out = _run("experiment", "record", str(folder))
    assert code == 0
    fields = {f["field"]: f for f in out["fields"]}
    assert fields["tip.measured_radius_before_nm"]["value"] is None
    assert fields["scan.direction"]["choices"] == ["trace", "retrace"]
    assert "sqrt(R)" in fields["tip.measured_radius_before_nm"]["meaning"]
    assert path.read_text() == before


# ------------------------------------------------------------------ upload


def _scan(tmp_path: Path, name: str = "scan-01.gsf", content: bytes = b"GSF raw bytes") -> Path:
    source = tmp_path / "instrument" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    return source


def test_upload_is_refused_before_the_lock(folder: Path, tmp_path: Path) -> None:
    code, out = _run("experiment", "upload", str(folder), str(_scan(tmp_path)))
    assert code == 1 and _kind(out) == "not_locked"
    assert not (folder / "during" / "raw" / "scan-01.gsf").exists()
    assert not (folder / "during" / "uploads.json").exists()


def test_upload_copies_hashes_and_records(locked: Path, tmp_path: Path) -> None:
    source = _scan(tmp_path)
    code, out = _run("experiment", "upload", str(locked), str(source))
    assert code == 0, out
    target = locked / "during" / "raw" / "scan-01.gsf"
    assert target.read_bytes() == source.read_bytes()
    assert out["sha256"] == file_sha256(source) == file_sha256(target)
    entries = json.loads((locked / "during" / "uploads.json").read_text())
    assert entries == [
        {"path": "scan-01.gsf", "sha256": out["sha256"], "bytes": 13, "at": entries[0]["at"]}
    ]


def test_upload_never_overwrites(locked: Path, tmp_path: Path) -> None:
    _run("experiment", "upload", str(locked), str(_scan(tmp_path)))
    other = _scan(tmp_path, "other.gsf", b"different bytes")
    code, out = _run("experiment", "upload", str(locked), str(other), "--as", "scan-01.gsf")
    assert code == 1 and _kind(out) == "already_exists"
    assert (locked / "during" / "raw" / "scan-01.gsf").read_bytes() == b"GSF raw bytes"


def test_upload_into_a_subfolder_by_name(locked: Path, tmp_path: Path) -> None:
    code, out = _run(
        "experiment", "upload", str(locked), str(_scan(tmp_path)), "--as", "staircase/S1-01.gsf"
    )
    assert code == 0, out
    assert (locked / "during" / "raw" / "staircase" / "S1-01.gsf").is_file()


@pytest.mark.parametrize(
    "name", ["../escape.gsf", "../../../escape.gsf", "/etc/escape", "a/../../b", ".hidden", ""]
)
def test_upload_refuses_a_name_outside_raw(locked: Path, tmp_path: Path, name: str) -> None:
    code, out = _run("experiment", "upload", str(locked), str(_scan(tmp_path)), "--as", name)
    assert code == 1 and _kind(out) == "outside_raw", out
    assert not (locked / "during" / "escape.gsf").exists()
    assert not (locked / "escape.gsf").exists()


def test_upload_refuses_a_symlink_out_of_raw(locked: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (locked / "during" / "raw" / "link").symlink_to(outside)
    code, out = _run(
        "experiment", "upload", str(locked), str(_scan(tmp_path)), "--as", "link/x.gsf"
    )
    assert code == 1 and _kind(out) == "outside_raw"
    assert not any(outside.iterdir())


def test_upload_of_a_missing_file_is_refused(locked: Path, tmp_path: Path) -> None:
    code, out = _run("experiment", "upload", str(locked), str(tmp_path / "nope.gsf"))
    assert code == 1 and _kind(out) == "missing_file"


# ------------------------------------------------------------------ commit


def test_commit_is_refused_before_the_lock(folder: Path) -> None:
    code, out = _run("experiment", "commit", str(folder), "--phase", "during")
    assert code == 1 and _kind(out) == "not_locked"


def test_commit_refuses_pre_as_a_phase(locked: Path) -> None:
    code, out = _run("experiment", "commit", str(locked), "--phase", "pre")
    assert code == 1 and _kind(out) == "invalid_phase"


def test_commit_during_then_nothing_to_commit(locked: Path, tmp_path: Path) -> None:
    _run("experiment", "upload", str(locked), str(_scan(tmp_path)))
    _run("experiment", "log", str(locked), "scan-01 from the first session")
    code, out = _run("experiment", "commit", str(locked), "--phase", "during", "-m", "session 1")
    assert code == 0, out
    assert out["commit"]["subject"] == "session 1"
    assert any(f.endswith("during/raw/scan-01.gsf") for f in out["files"])
    assert any(f.endswith("during/uploads.json") for f in out["files"])
    code, out = _run("experiment", "commit", str(locked), "--phase", "during")
    assert code == 1 and _kind(out) == "nothing_to_commit"
    # Now the raw file's time comes from git, not from the filesystem.
    record = check(locked)
    assert record.first_raw is not None and record.first_raw.source == "git"


def test_commit_refuses_while_pre_has_changed_since_the_lock(locked: Path) -> None:
    with (locked / "pre" / "protocol.md").open("a") as handle:
        handle.write("edited after the lock\n")
    code, out = _run("experiment", "commit", str(locked), "--phase", "during")
    assert code == 1 and _kind(out) == "pre_changed"


def test_a_raw_file_git_ignores_is_named_and_its_hash_committed(
    locked: Path, repo: Path, tmp_path: Path
) -> None:
    (repo / ".gitignore").write_text("*.tiff\n")
    code, out = _run("experiment", "upload", str(locked), str(_scan(tmp_path, "big.tiff")))
    assert code == 0 and out["ignored_by_git"] is True
    code, out = _run("experiment", "commit", str(locked), "--phase", "during")
    assert code == 0, out
    assert out["ignored_by_git"] == ["during/raw/big.tiff"]
    committed = _git(locked, "show", "HEAD:./during/uploads.json")
    assert json.loads(committed)[0]["path"] == "big.tiff"


# ------------------------------------------------------------------ status


def test_status_walks_the_steps_in_order(folder: Path, tmp_path: Path) -> None:
    def states() -> dict[str, str]:
        out = _run("experiment", "status", str(folder))[1]
        return {s["step"]: s["state"] for s in out["steps"]}

    assert states()["gate"] == "next"
    assert states()["lock"] == "blocked"
    _run("experiment", "criterion", str(folder), "x")
    assert states()["lock"] == "next"
    assert states()["data"] == "blocked"
    _run("experiment", "lock", str(folder))
    assert states()["lock"] == "done" and states()["data"] == "next"
    _run("experiment", "upload", str(folder), str(_scan(tmp_path)))
    assert states()["commit_during"] == "next"
    _run("experiment", "commit", str(folder), "--phase", "during")
    after = states()
    assert after["commit_during"] == "done" and after["analyse"] == "next"
    status = _run("experiment", "status", str(folder))[1]
    assert [a["command"] for a in status["analyses"]] == [
        "experiment report",
        "experiment folding-screen",
    ]
    assert status["raw"][0]["sha256"] == file_sha256(folder / "during" / "raw" / "scan-01.gsf")


def test_status_of_a_folder_that_is_not_one(tmp_path: Path) -> None:
    code, out = _run("experiment", "status", str(tmp_path))
    assert code == 1 and _kind(out) == "missing_folder"


def test_every_analysis_named_is_a_real_command() -> None:
    import typer

    from dobladillo.experiments.lifecycle import ANALYSES

    cli = typer.main.get_command(app)
    for analyses in ANALYSES.values():
        for analysis in analyses:
            group, name = analysis.command
            assert name in cli.commands[group].commands, analysis.command  # type: ignore[attr-defined]
            assert (Path(__file__).resolve().parent.parent / analysis.protocol).is_file()


def test_staple_source_and_purification_are_recorded(folder: Path) -> None:
    """Recycled staples (a pool recovered from an earlier fold's purification)
    are recorded with their pool, cycle and top-up; the purification records
    whether the excess was kept, and under which label."""
    code, out = _run(
        "experiment", "record", str(folder),
        "--set", "staples.source=recycled",
        "--set", "staples.pool=E1-PEG-2026-10-01",
        "--set", "staples.reuse_cycle=1",
        "--set", "staples.topped_up=1x of the consumed staples, fresh",
        "--set", "purification.method=PEG precipitation",
        "--set", "purification.excess_kept=true",
        "--set", "purification.kept_as=E2-PEG-2026-10-08",
    )  # fmt: skip
    assert code == 0, out
    data = json.loads((folder / "during" / "instrument.json").read_text())
    assert data["staples"]["source"] == "recycled" and data["staples"]["reuse_cycle"] == 1
    assert data["purification"]["excess_kept"] is True

    from dobladillo.experiments.layout import staples_summary

    summary = staples_summary(folder)
    assert summary is not None and "RECYCLED" in summary and "E1-PEG-2026-10-01" in summary


@pytest.mark.parametrize(
    "assignment",
    ["staples.source=reused", "staples.reuse_cycle=0", "purification.method=magic"],
)
def test_staple_fields_refuse_what_they_do_not_accept(folder: Path, assignment: str) -> None:
    code, out = _run("experiment", "record", str(folder), "--set", assignment)
    assert code != 0 and _kind(out) == "invalid_value", out


def test_recycled_staples_without_a_pool_are_a_record_problem(folder: Path) -> None:
    from dobladillo.experiments.layout import check

    _run("experiment", "record", str(folder), "--set", "staples.source=recycled")
    assert any("no pool is named" in p for p in check(folder).problems)
    _run("experiment", "record", str(folder), "--set", "staples.pool=E1-PEG-2026-10-01")
    assert not any("no pool is named" in p for p in check(folder).problems)
    _run("experiment", "record", str(folder), "--set", "staples.source=fresh")
    assert not any("no pool is named" in p for p in check(folder).problems)

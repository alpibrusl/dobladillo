"""The queue, exercised against a stand-in for oxDNA.

A real stage is hours, so these tests run a script that writes the energy trace
the input file promises and exits. That is enough to exercise everything the
queue is responsible for -- ordering, parallelism, restart, failure -- and none
of what oxDNA is responsible for.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from dobladillo.sim.queue import (
    CORES_HELD_BACK,
    STAGES,
    default_workers,
    enqueue,
    load,
    run,
    stage_complete,
    stage_progress,
    status,
)

STUB = textwrap.dedent("""
    import os, sys, pathlib, time
    settings = {}
    for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            settings[k.strip()] = v.strip()
    here = pathlib.Path.cwd()
    if os.environ.get("FAIL_STAGE") and os.environ["FAIL_STAGE"] in sys.argv[1]:
        sys.exit(3)
    if os.environ.get("MARK_CONCURRENCY"):
        marker = here / "running.marker"
        marker.write_text("x")
        peak = pathlib.Path(os.environ["MARK_CONCURRENCY"])
        live = len(list(peak.parent.glob("*/running.marker")))
        prior = int(peak.read_text()) if peak.exists() else 0
        peak.write_text(str(max(prior, live)))
        time.sleep(0.15)
        marker.unlink()
    steps, dt = int(settings["steps"]), float(settings.get("dt", "0.003"))
    with pathlib.Path(settings["energy_file"]).open("w") as f:
        f.write(f"  {steps * dt:.4f}  -1.5  0.29  -1.2\\n")
    pathlib.Path(settings["lastconf_file"]).write_text("t = 0\\n")
""")


@pytest.fixture
def stub(tmp_path: Path) -> str:
    path = tmp_path / "stub_oxdna.py"
    path.write_text("#!/usr/bin/env python3\n" + STUB)
    path.chmod(0o755)
    return str(path)


def _bundle(directory: Path, *, steps: int = 1000) -> Path:
    """The parts of a bundle the queue actually reads."""
    directory.mkdir(parents=True, exist_ok=True)
    for i, stage in enumerate(STAGES):
        previous = f"conf_{STAGES[i - 1]}.dat" if i else "start.dat"
        (directory / f"input_{stage}").write_text(
            f"dt = 0.003\nsteps = {steps}\nconf_file = {previous}\n"
            f"lastconf_file = conf_{stage}.dat\n"
            f"energy_file = energy_traj_{stage}.dat\n"
            f"trajectory_file = traj_{stage}.dat\n"
        )
    (directory / "start.dat").write_text("t = 0\n")
    return directory


def test_workers_leave_the_machine_usable() -> None:
    """Saturating every core makes the desktop unusable and buys little once
    the queue is already deep."""
    assert default_workers() >= 1
    assert default_workers() <= max(1, __import__("os").cpu_count() - CORES_HELD_BACK)


def test_enqueue_refuses_something_that_is_not_a_bundle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not look like a job bundle"):
        enqueue(tmp_path / "q", tmp_path / "empty")


def test_a_queued_job_starts_nothing(tmp_path: Path) -> None:
    job = enqueue(tmp_path / "q", _bundle(tmp_path / "b"))
    assert job.state == "queued"
    assert not (tmp_path / "b" / "conf_01_mc.dat").exists()


def test_running_the_queue_runs_every_stage_in_order(tmp_path: Path, stub: str) -> None:
    bundle = _bundle(tmp_path / "b")
    enqueue(tmp_path / "q", bundle)
    outcome = run(tmp_path / "q", oxdna=stub, workers=2, poll_seconds=0.01, once=True)
    assert outcome["finished"] == 1
    for stage in STAGES:
        assert (bundle / f"conf_{stage}.dat").exists(), f"{stage} did not run"
    assert load(tmp_path / "q")[0].state == "done"


def test_a_finished_bundle_is_not_run_again(tmp_path: Path, stub: str) -> None:
    """Restartability. A bundle whose first three stages finished before the
    runner was killed should resume at production, not redo six hours."""
    bundle = _bundle(tmp_path / "b")
    enqueue(tmp_path / "q", bundle)
    run(tmp_path / "q", oxdna=stub, workers=1, poll_seconds=0.01, once=True)
    stamps = {s: (bundle / f"conf_{s}.dat").stat().st_mtime_ns for s in STAGES}

    enqueue(tmp_path / "q", bundle)
    run(tmp_path / "q", oxdna=stub, workers=1, poll_seconds=0.01, once=True)
    after = {s: (bundle / f"conf_{s}.dat").stat().st_mtime_ns for s in STAGES}
    assert after == stamps, "a completed stage was run again"


def test_a_failing_stage_is_recorded_with_where_to_look(tmp_path: Path, stub: str) -> None:
    import os

    bundle = _bundle(tmp_path / "b")
    enqueue(tmp_path / "q", bundle)
    os.environ["FAIL_STAGE"] = "03_md_released"
    try:
        run(tmp_path / "q", oxdna=stub, workers=1, poll_seconds=0.01, once=True)
    finally:
        del os.environ["FAIL_STAGE"]
    job = load(tmp_path / "q")[0]
    assert job.state == "failed"
    assert "03_md_released" in job.error
    assert ".log" in job.error


def test_jobs_really_do_run_in_parallel(tmp_path: Path, stub: str) -> None:
    """The whole justification for the module. oxDNA's CPU backend is
    single-threaded, so if the queue did not overlap jobs it would be a
    more complicated way of writing a for loop."""
    import os

    peak = tmp_path / "peak.txt"
    for i in range(4):
        enqueue(tmp_path / "q", _bundle(tmp_path / f"b{i}"))
    os.environ["MARK_CONCURRENCY"] = str(peak)
    try:
        run(tmp_path / "q", oxdna=stub, workers=4, poll_seconds=0.01, once=True)
    finally:
        del os.environ["MARK_CONCURRENCY"]
    assert int(peak.read_text()) >= 2, "no two jobs were ever running at once"


def test_progress_is_read_from_the_bundle_not_from_stdout(tmp_path: Path, stub: str) -> None:
    """stdout belongs to whoever launched the process; the energy trace
    belongs to the bundle, so status works for a run someone else started."""
    bundle = _bundle(tmp_path / "b", steps=4000)
    assert stage_progress(bundle, "01_mc") == (0, 4000)
    assert not stage_complete(bundle, "01_mc")
    enqueue(tmp_path / "q", bundle)
    run(tmp_path / "q", oxdna=stub, workers=1, poll_seconds=0.01, once=True)
    assert stage_progress(bundle, "01_mc") == (4000, 4000)
    assert stage_complete(bundle, "01_mc")


def test_status_is_json_and_survives_an_empty_queue(tmp_path: Path) -> None:
    payload = status(tmp_path / "q")
    assert payload["counts"] == {}
    json.dumps(payload)


def test_one_file_per_job_so_a_runner_and_a_caller_never_collide(tmp_path: Path) -> None:
    a = enqueue(tmp_path / "q", _bundle(tmp_path / "a"))
    b = enqueue(tmp_path / "q", _bundle(tmp_path / "b"))
    files = sorted(p.name for p in (tmp_path / "q" / "jobs").glob("*.json"))
    assert files == sorted([f"{a.id}.json", f"{b.id}.json"])


def test_progress_reads_whichever_trace_got_further(tmp_path: Path, stub: str) -> None:
    """Found on a live run. A bundle whose `steps` was edited after generation
    keeps the energy interval computed from the ORIGINAL count, so the energy
    trace held one line while the trajectory held sixty frames. Status read 0%,
    and `stage_complete` would have let a restart redo the work.
    """
    bundle = _bundle(tmp_path / "b", steps=100_000)
    stage = STAGES[3]
    settings = (bundle / f"input_{stage}").read_text()
    (bundle / f"input_{stage}").write_text(settings + "print_conf_interval = 1000\n")

    # Energy silent, trajectory two-thirds of the way through.
    (bundle / f"energy_traj_{stage}.dat").write_text("  0.0000  -1.5  0.29  -1.2\n")
    (bundle / f"traj_{stage}.dat").write_text(
        "".join(f"t = {i * 1000}\nb = 1 1 1\n" for i in range(68))
    )

    done, total = stage_progress(bundle, stage)
    assert total == 100_000
    assert done == pytest.approx(67_000, abs=1000), "the trajectory was ignored"
    assert not stage_complete(bundle, stage)

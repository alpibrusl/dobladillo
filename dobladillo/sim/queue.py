"""A work queue for oxDNA bundles, because one core was doing all the work.

`write_job_bundle` says executing a bundle is the human's job, on a machine
with the backend it asks for. That was written when the backend was expected to
be a GPU somewhere else. On this machine the backend is a CPU, and oxDNA's CPU
backend is **single-threaded**: a production run holds 99% of one core and 43
MB, and leaves the other fifteen idle for six and a half hours.

That is the argument for this module, and it is not about scheduling
convenience. The next experiment the hinge needs is a sweep -- of joint length,
to find out whether the latch can reach -- and a sweep run one job at a time is
a week. Run eight at a time it is one night, on hardware that is already here.

The shape is deliberately small. Each bundle's stages are strictly sequential,
because every stage starts from the previous stage's last configuration. Across
bundles there is no dependency at all, so that is where the parallelism is.

One file per job rather than one file for the queue: adding work is creating a
file and updating status is writing that job's own file, so a runner and a
caller never write the same file and there is no lock to get wrong.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

#: The stage chain, in the only order it can run in.
STAGES: Final = ("01_mc", "02_md_trapped", "03_md_released", "04_production")

#: Leave this many cores alone. The machine is somebody's desktop and is also
#: driving other things; saturating every core makes it unusable and buys
#: proportionally little once the queue is already several jobs deep.
CORES_HELD_BACK: Final = 4

#: How often the runner looks for newly queued work, seconds. Jobs run for
#: hours, so this can be lazy; it only bounds how long a new job waits for a
#: free worker that already exists.
POLL_SECONDS: Final = 10.0

State = Literal["queued", "running", "done", "failed"]

#: Where runs and queues live unless told otherwise: $DOBLADILLO_RUNS, else a
#: directory next to the checkout. Not the repository -- trajectories are
#: hundreds of MB each -- and never a temp directory: two sets of results,
#: the corrected hinge joint sweep among them, were lost when a session's
#: temporary directory was cleaned (#16).
RUNS_ROOT: Final = Path(
    os.environ.get("DOBLADILLO_RUNS", "~/Workspace/bio/dobladillo-runs")
).expanduser()

#: Directory prefixes that get cleaned without asking.
_TEMP_PREFIXES: Final = ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders")


def temp_root_warning(path: Path) -> str | None:
    """A warning if `path` sits somewhere that is cleaned without asking."""
    import tempfile

    resolved = str(path.expanduser().resolve())
    prefixes = (*_TEMP_PREFIXES, str(Path(tempfile.gettempdir()).resolve()))
    if any(resolved == p or resolved.startswith(p.rstrip("/") + "/") for p in prefixes):
        return (
            f"{path} is under a temporary directory and may be deleted without warning; "
            f"runs take hours, so keep them under {RUNS_ROOT} or set $DOBLADILLO_RUNS"
        )
    return None


def default_workers() -> int:
    """Performance cores minus the ones held back, at least one."""
    try:
        cores = int(os.sysconf("SC_NPROCESSORS_ONLN"))
    except (ValueError, OSError):  # pragma: no cover - platform dependent
        cores = 4
    return max(1, cores - CORES_HELD_BACK)


@dataclass
class Job:
    """One bundle, and where it has got to."""

    id: str
    bundle: str
    state: State = "queued"
    stage: str | None = None
    error: str | None = None
    enqueued_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    label: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return Path(self.bundle)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["progress"] = progress(self.directory)
        return payload


def _jobs_dir(root: Path) -> Path:
    directory = root / "jobs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write(root: Path, job: Job) -> None:
    path = _jobs_dir(root) / f"{job.id}.json"
    # Write and rename, so a reader never sees a half-written job.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(job), indent=2))
    temporary.replace(path)


def enqueue(
    root: Path, bundle: Path, *, label: str = "", meta: dict[str, Any] | None = None
) -> Job:
    """Add a bundle to the queue. Does not start anything."""
    bundle = bundle.resolve()
    if not (bundle / f"input_{STAGES[0]}").exists():
        raise ValueError(f"{bundle} does not look like a job bundle: no input_{STAGES[0]}")
    job = Job(
        id=uuid.uuid4().hex[:12],
        bundle=str(bundle),
        enqueued_at=time.time(),
        label=label or bundle.name,
        meta=meta or {},
    )
    _write(root, job)
    return job


def load(root: Path) -> list[Job]:
    """Every job, oldest first. Unreadable entries are skipped, not raised on:
    a runner mid-write should not break a status call."""
    jobs = []
    for path in sorted(_jobs_dir(root).glob("*.json")):
        try:
            jobs.append(Job(**json.loads(path.read_text())))
        except (json.JSONDecodeError, TypeError, OSError):  # pragma: no cover - racy
            continue
    return sorted(jobs, key=lambda j: j.enqueued_at)


def _stage_settings(directory: Path, stage: str) -> dict[str, str]:
    text = (directory / f"input_{stage}").read_text()
    settings = {}
    for line in text.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip()
    return settings


def stage_progress(directory: Path, stage: str) -> tuple[int, int]:
    """(steps done, steps asked for) for one stage.

    Read from the energy trace rather than from stdout, because stdout belongs
    to whoever launched the process and the energy file belongs to the bundle.
    Its first column is simulation time, so steps is time over dt.
    """
    try:
        settings = _stage_settings(directory, stage)
        total = int(settings["steps"])
    except (OSError, KeyError, ValueError):
        return (0, 0)
    # Whichever of the two traces has got further. They are written at
    # independent intervals, and reading only the energy one is fragile: a
    # bundle whose `steps` was edited after generation keeps the energy
    # interval computed from the original count, so the trace can hold a
    # single line while the trajectory holds sixty frames. That reads as 0%
    # in `status`, and worse, `stage_complete` then lets a restart redo work
    # that was done.
    done = 0
    dt = float(settings.get("dt", "0.003") or 0.003)

    energy = directory / settings.get("energy_file", f"energy_traj_{stage}.dat")
    if energy.exists() and dt:
        try:
            lines = [ln for ln in energy.read_text().splitlines() if ln.strip()]
            if lines:
                done = max(done, int(round(float(lines[-1].split()[0]) / dt)))
        except (OSError, ValueError, IndexError):  # pragma: no cover - partial write
            pass

    trajectory = directory / settings.get("trajectory_file", f"traj_{stage}.dat")
    interval = settings.get("print_conf_interval")
    if trajectory.exists() and interval:
        try:
            frames = trajectory.read_text().count("\nt = ") + 1
            done = max(done, (frames - 1) * int(interval))
        except (OSError, ValueError):  # pragma: no cover - partial write
            pass

    return (min(done, total), total)


def stage_complete(directory: Path, stage: str) -> bool:
    """Whether a stage has already run to its full step count.

    This is what makes the queue restartable. A bundle whose first three stages
    finished before the runner was killed resumes at production rather than
    spending six hours redoing relaxation.
    """
    done, total = stage_progress(directory, stage)
    return total > 0 and done >= total


def progress(directory: Path) -> dict[str, Any]:
    """Per-stage progress for a bundle, for status output."""
    stages = {}
    for stage in STAGES:
        done, total = stage_progress(directory, stage)
        stages[stage] = {"steps": done, "of": total}
    return stages


def stage_binary(directory: Path, stage: str, *, oxdna: str) -> str | None:
    """The binary a stage needs: the Metal build for a Metal stage, else `oxdna`.

    A Metal bundle runs its Monte Carlo stage on the CPU and the rest on the
    GPU, so one bundle needs both. None when the stage wants Metal and no Metal
    binary is configured.
    """
    if _stage_settings(directory, stage).get("backend") == "Metal":
        from dobladillo.sim.jobs import metal_binary

        return metal_binary()
    return oxdna


def run_stage(directory: Path, stage: str, *, oxdna: str) -> subprocess.Popen[bytes]:
    """Start one stage. The caller owns waiting for it."""
    binary = stage_binary(directory, stage, oxdna=oxdna)
    if binary is None:
        from dobladillo.sim.jobs import METAL_BINARY_ENV

        raise FileNotFoundError(f"stage {stage} runs on Metal; set ${METAL_BINARY_ENV}")
    log = (directory / f"{stage}.log").open("ab")
    return subprocess.Popen(
        [binary, f"input_{stage}"], cwd=directory, stdout=log, stderr=subprocess.STDOUT
    )


def _start(root: Path, job: Job, index: int, *, oxdna: str) -> subprocess.Popen[bytes] | None:
    """Start a job's stage, or record the job as failed when it cannot start."""
    try:
        return run_stage(job.directory, STAGES[index], oxdna=oxdna)
    except OSError as e:
        job.state = "failed"
        job.error = str(e)
        job.finished_at = time.time()
        _write(root, job)
        return None


def run(
    root: Path,
    *,
    oxdna: str,
    workers: int | None = None,
    poll_seconds: float = POLL_SECONDS,
    once: bool = False,
) -> dict[str, Any]:
    """Run the queue until it is empty.

    Blocking. Launch it with nohup and watch it with `status`; there is no
    daemon and no supervision, because a supervisor that can restart a six
    hour job unattended is a thing to want only after something has actually
    gone wrong in a way restarting would fix.

    `once` drains what is queued now and returns rather than waiting for more,
    which is what a test wants and what a one-shot sweep wants.
    """
    workers = workers or default_workers()
    running: dict[str, tuple[Job, int, subprocess.Popen[bytes]]] = {}
    finished = 0

    while True:
        for job_id, (job, index, process) in list(running.items()):
            code = process.poll()
            if code is None:
                continue
            del running[job_id]
            if code != 0:
                job.state = "failed"
                job.error = f"stage {STAGES[index]} exited {code}; see {STAGES[index]}.log"
                job.finished_at = time.time()
                _write(root, job)
                finished += 1
                continue
            index += 1
            while index < len(STAGES) and stage_complete(job.directory, STAGES[index]):
                index += 1
            if index >= len(STAGES):
                job.state = "done"
                job.stage = None
                job.finished_at = time.time()
                _write(root, job)
                finished += 1
                continue
            job.stage = STAGES[index]
            _write(root, job)
            process = _start(root, job, index, oxdna=oxdna)
            if process is None:
                finished += 1
                continue
            running[job_id] = (job, index, process)

        queued = [j for j in load(root) if j.state == "queued"]
        while queued and len(running) < workers:
            job = queued.pop(0)
            index = 0
            while index < len(STAGES) and stage_complete(job.directory, STAGES[index]):
                index += 1
            job.started_at = time.time()
            if index >= len(STAGES):
                job.state = "done"
                job.finished_at = job.started_at
                _write(root, job)
                finished += 1
                continue
            job.state = "running"
            job.stage = STAGES[index]
            _write(root, job)
            process = _start(root, job, index, oxdna=oxdna)
            if process is None:
                finished += 1
                continue
            running[job.id] = (job, index, process)

        if not running and not queued:
            break
        if once and not running:
            break
        time.sleep(poll_seconds)

    return {"finished": finished, "workers": workers}


def status(root: Path) -> dict[str, Any]:
    """What the queue is doing, as data."""
    jobs = load(root)
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.state] = counts.get(job.state, 0) + 1
    return {
        "root": str(root),
        "workers_available": default_workers(),
        "counts": counts,
        "jobs": [job.as_dict() for job in jobs],
    }

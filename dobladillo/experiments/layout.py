"""The shape of an experiment on disk: what is fixed before, during and after.

An experiment run here crosses two people and several days, so the thing that
matters is not the folders. It is that **the prediction is written down before
the data exists**.

Without that, the closed loop is not a test. `compare` will happily reconcile a
measurement with whatever the toolchain currently predicts, and if the
prediction was adjusted after seeing a scan -- or if a part's defaults changed
in between -- nothing in the numbers would say so. The comparison would look
identical either way. That is the failure this layout is built to make visible
rather than to trust people not to commit.

So: `pre/prediction.json` records what was expected, `check` reports when it
was recorded against when the raw data was, and `post/` compares against the
recorded prediction rather than against a freshly computed one. If the part's
defaults change next month, an old experiment still reports what it actually
predicted at the time.

Timestamps come from git where the file is tracked, because a commit time is
evidence and a modification time is not: cloning a repository resets every
mtime to the moment of checkout, which would make a naive check pass for
everyone and mean nothing.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

Phase = Literal["pre", "during", "post"]

PHASES: Final[tuple[Phase, ...]] = ("pre", "during", "post")

#: What each phase is for, in the words a person opening the folder needs.
PURPOSE: Final[dict[Phase, str]] = {
    "pre": "Everything fixed before the first sample exists: the plan, the "
    "predictions, what to order, and the protocol to follow.",
    "during": "What actually happened: the session log, the instrument's state, "
    "and the raw files exactly as the instrument wrote them.",
    "post": "Produced by the toolchain from the two above. Nothing here is edited by hand.",
}

#: Files a phase needs before it counts as complete. Directories end in "/" and
#: are satisfied by containing at least one file.
REQUIRED: Final[dict[Phase, tuple[str, ...]]] = {
    "pre": ("plan.md", "prediction.json", "protocol.md", "order/"),
    "during": ("log.md", "instrument.json", "raw/"),
    "post": ("measurements.json", "comparison.json", "report.md"),
}

#: Written into `during/raw/` so the folder is not empty and so the rule about
#: it is stated where someone will actually read it.
RAW_NOTE: Final = """\
Raw instrument files, exactly as written. Do not edit, crop, rename or convert
anything in this directory.

Export a copy to .gsf for the toolchain and put that here too -- alongside the
native file, not instead of it. `dobladillo afm read` will tell you whether the
pixel size and height units came through, which is worth checking before
believing any dimension downstream.
"""


@dataclass(frozen=True)
class Recorded:
    """When a path entered the record, and how well that is known."""

    path: Path
    timestamp: float | None
    source: Literal["git", "filesystem", "missing"]

    @property
    def trustworthy(self) -> bool:
        return self.source == "git"


def _git_time(path: Path) -> float | None:
    """Commit time of the last change to `path`, or None if untracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - platform
        return None
    value = out.stdout.strip()
    return float(value) if out.returncode == 0 and value else None


def recorded_at(path: Path) -> Recorded:
    """When `path` was recorded, preferring git over the filesystem."""
    if not path.exists():
        return Recorded(path=path, timestamp=None, source="missing")
    committed = _git_time(path)
    if committed is not None:
        return Recorded(path=path, timestamp=committed, source="git")
    return Recorded(path=path, timestamp=path.stat().st_mtime, source="filesystem")


def _earliest(directory: Path) -> Recorded | None:
    candidates = [
        recorded_at(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "README.md"
    ]
    dated = [c for c in candidates if c.timestamp is not None]
    return min(dated, key=lambda c: c.timestamp or 0.0) if dated else None


@dataclass(frozen=True)
class PhaseState:
    phase: Phase
    present: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def started(self) -> bool:
        return bool(self.present)

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "complete": self.complete,
            "started": self.started,
            "present": list(self.present),
            "missing": list(self.missing),
        }


@dataclass(frozen=True)
class Check:
    """Whether an experiment folder is in a state its results can be believed in."""

    root: Path
    phases: tuple[PhaseState, ...]
    prediction: Recorded | None = None
    first_raw: Recorded | None = None
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready_for(self) -> Phase | None:
        """The next phase that may be started, or None when finished."""
        for state, phase in zip(self.phases, PHASES, strict=True):
            if not state.complete:
                return phase
        return None

    @property
    def results_believable(self) -> bool:
        return not self.problems and all(p.complete for p in self.phases[:2])

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "phases": [p.as_dict() for p in self.phases],
            "ready_for": self.ready_for,
            "results_believable": self.results_believable,
            "prediction_recorded": (
                None
                if self.prediction is None
                else {"source": self.prediction.source, "at": self.prediction.timestamp}
            ),
            "first_raw_recorded": (
                None
                if self.first_raw is None
                else {"source": self.first_raw.source, "at": self.first_raw.timestamp}
            ),
            "problems": list(self.problems),
        }


def check(root: Path) -> Check:
    """Inspect an experiment folder.

    The pre-registration test is the part worth reading: if the prediction was
    recorded after the first raw file, the experiment may still be perfectly
    good science, but its comparison is no longer a prediction and the report
    says so rather than leaving it to be noticed.
    """
    states = []
    for phase in PHASES:
        directory = root / phase
        present: list[str] = []
        missing: list[str] = []
        for item in REQUIRED[phase]:
            if item.endswith("/"):
                sub = directory / item.rstrip("/")
                ok = sub.is_dir() and any(
                    p.is_file() and p.name != "README.md" for p in sub.rglob("*")
                )
            else:
                ok = (directory / item).is_file()
            (present if ok else missing).append(item)
        states.append(PhaseState(phase=phase, present=tuple(present), missing=tuple(missing)))

    prediction = recorded_at(root / "pre" / "prediction.json")
    first_raw = _earliest(root / "during" / "raw") if (root / "during" / "raw").is_dir() else None

    problems: list[str] = []
    if prediction.source == "missing":
        problems.append("no pre/prediction.json: nothing was predicted, so nothing can be tested")
    elif first_raw and first_raw.timestamp and prediction.timestamp:
        if prediction.timestamp > first_raw.timestamp:
            problems.append(
                "pre/prediction.json was recorded AFTER the first raw file. The comparison "
                "in post/ is a description, not a prediction, and should be reported as one"
            )
        elif prediction.timestamp == first_raw.timestamp:
            # Git commit times have one-second granularity, so this is a tie
            # rather than an ordering. It cannot happen across a real
            # experiment and can happen easily in a script, which is exactly
            # when silence would be wrong.
            problems.append(
                "pre/prediction.json and the first raw file carry the same timestamp, so "
                "which came first cannot be established. Commit pre/ as its own commit, "
                "before the session"
            )
        elif not prediction.trustworthy or not first_raw.trustworthy:
            problems.append(
                "the prediction appears to predate the data, but one of the two timestamps "
                "comes from the filesystem rather than from git, and a clone resets those. "
                "Commit pre/ before taking data and this becomes evidence"
            )

    return Check(
        root=root,
        phases=tuple(states),
        prediction=prediction if prediction.source != "missing" else None,
        first_raw=first_raw,
        problems=tuple(problems),
    )


def scaffold(
    root: Path, *, slug: str, prediction: dict[str, Any], plan: str, protocol: str
) -> Path:
    """Create an experiment folder. Refuses to overwrite one."""
    directory = root / slug
    if directory.exists():
        raise FileExistsError(f"{directory} already exists; pick another name or work in it")

    for phase in PHASES:
        (directory / phase).mkdir(parents=True)
        (directory / phase / "README.md").write_text(f"# {phase}\n\n{PURPOSE[phase]}\n")
    (directory / "pre" / "order").mkdir()
    (directory / "during" / "raw").mkdir()
    (directory / "during" / "raw" / "README.md").write_text(RAW_NOTE)

    (directory / "pre" / "plan.md").write_text(plan)
    (directory / "pre" / "protocol.md").write_text(protocol)
    (directory / "pre" / "prediction.json").write_text(json.dumps(prediction, indent=2) + "\n")
    (directory / "during" / "log.md").write_text(SESSION_LOG_TEMPLATE)
    (directory / "during" / "instrument.json").write_text(
        json.dumps(INSTRUMENT_TEMPLATE, indent=2) + "\n"
    )
    return directory


SESSION_LOG_TEMPLATE: Final = """\
# Session log

One entry per session. Written as it happens, not reconstructed afterwards --
a deviation nobody recorded is indistinguishable from one that did not occur,
and the deviations are usually where the interesting results come from.

## <date> — <who>

**Deviations from `pre/protocol.md`.** Anything at all. "Used the older buffer
because the new one was not made up yet" is exactly the kind of note that
explains an anomaly three weeks later.

- 

**Observations.** Gel looks right? Sample sticking? Tip picked something up?

- 

**Files written this session.** Which raw files came from this session, so a
scan can be traced to the conditions it was taken under.

- 
"""

#: Fields the analysis actually consumes, plus the ones that explain a result
#: when it goes wrong. `tip_radius_nm` is not optional: it enters every width
#: as a square root and is the dominant systematic in anything this measures.
INSTRUMENT_TEMPLATE: Final[dict[str, Any]] = {
    "instrument": "",
    "mode": "",
    "tip": {
        "part_number": "",
        "nominal_radius_nm": None,
        "measured_radius_before_nm": None,
        "measured_radius_after_nm": None,
        "measured_radius_between_nm": None,
        "note": "Measure it. A nominal 10 nm tip is routinely 8-20 nm in use, and "
        "the correction goes as sqrt(R). Before AND after: a tip that blunted "
        "mid-session makes early and late scans differently wrong. Two-arm "
        "experiments (E2) also measure it BETWEEN the arms.",
    },
    "imaging_order": None,
    "reference": {"flat_height_nm": None, "from": ""},
    "buffer": {"tris_mm": None, "edta_mm": None, "mgcl2_mm": None, "ph": None},
    "temperature_c": None,
    "scan": {"size_nm": None, "pixels": None, "rate_hz": None},
}

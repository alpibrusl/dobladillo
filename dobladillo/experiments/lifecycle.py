"""The experimentalist's acts on a folder: gate, lock, log, record, upload, commit.

`layout` says what a folder must hold and `check` whether its record can be
believed. This module is how the record gets written, one act at a time, by
the person running the experiment -- from the CLI (`experiment criterion`,
`lock`, `log`, `record`, `upload`, `commit`) or from the local web UI, which
runs those same commands and nothing else.

**These are human acts.** Each one writes a gate, a reading, raw data or a
commit, and each is in `mcp_server.FORBIDDEN_COMMANDS`: an agent may check
and analyse a folder, never write its record (`experiments/AGENTS.md`).

**The lock is a commit.** `layout`'s docstring says why: git's commit time is
evidence and a file's modification time is not. So `lock` commits `pre/`
with the gate written in it, and "locked" means exactly that: the committed
`pre/plan.md` (or `pre/prediction.json`) carries a gate. It is read from the
commit, not from the working copy, so editing the file after the lock does
not unlock anything; it shows up as a change to `pre/` instead.

**Every act refuses rather than repairs.** A refusal is `Refused` with a
stable `kind`, which the CLI turns into `{"error": {"kind", "message"}}`:
a gate after the lock, raw data before it, a raw file that already exists, a
reading that is not one. Nothing here fills in a value, renames a file to
make room, or retries.

Git runs as a subprocess with an argument list, never a shell string, from
inside the folder, and commits carry the local git identity. A later
multi-user front end passes `author` through; nothing else changes.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from dobladillo.experiments.layout import (
    CRITERION_LINE,
    INSTRUMENT_TEMPLATE,
    plan_criterion,
    prediction_criterion,
)


class Refused(Exception):
    """An act the record does not allow. `kind` is stable, for a caller to branch on."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


#: Where `upload` records what it copied: outside `during/raw/`, so the record
#: is not mistaken for data, and committed with `during/`, so a raw file git
#: ignores (`.gitignore` keeps large images out) still has its hash on record.
UPLOADS: Final = "uploads.json"


# --------------------------------------------------------------------- git


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in `cwd`. An argument list, never a shell; no prompt can block it."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as e:  # git missing, or hung
        return subprocess.CompletedProcess(["git", *args], 128, "", str(e))


def repository(folder: Path) -> Path | None:
    """The git work tree `folder` is in, or None."""
    if not folder.is_dir():
        return None
    out = _git(folder, "rev-parse", "--show-toplevel")
    value = out.stdout.strip()
    return Path(value) if out.returncode == 0 and value else None


@dataclass(frozen=True)
class Commit:
    sha: str
    at: float
    author: str
    subject: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sha": self.sha,
            "short": self.sha[:10],
            "at": self.at,
            "at_iso": _iso(self.at),
            "author": self.author,
            "subject": self.subject,
        }


def _iso(timestamp: float) -> str:
    return _dt.datetime.fromtimestamp(timestamp, _dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def last_commit(folder: Path, path: str) -> Commit | None:
    """The last commit that touched `path` (relative to `folder`), or None."""
    out = _git(folder, "log", "-1", "--format=%H%x1f%ct%x1f%an <%ae>%x1f%s", "--", path)
    fields = out.stdout.strip().split("\x1f")
    if out.returncode != 0 or len(fields) != 4:
        return None
    return Commit(sha=fields[0], at=float(fields[1]), author=fields[2], subject=fields[3])


def _committed(folder: Path, relative: str) -> str | None:
    """A file's text as of HEAD, or None when it is not committed."""
    out = _git(folder, "show", f"HEAD:./{relative}")
    return out.stdout if out.returncode == 0 else None


def _changed(folder: Path, path: str) -> tuple[str, ...]:
    """Paths under `path` that differ from HEAD, untracked ones included."""
    out = _git(folder, "status", "--porcelain", "--untracked-files=all", "--", path)
    if out.returncode != 0:
        return ()
    return tuple(line[3:] for line in out.stdout.splitlines() if len(line) > 3)


def _ignored(folder: Path, paths: list[str]) -> list[str]:
    """Which of `paths` (relative to `folder`) git ignores, and so will not commit."""
    if not paths:
        return []
    out = _git(folder, "check-ignore", "--", *paths)
    return out.stdout.splitlines() if out.returncode == 0 else []


def _commit(
    folder: Path, path: str, *, message: str, author: str | None
) -> tuple[Commit, list[str]]:
    """Stage and commit `path` alone; other staged work is left as it was."""
    added = _git(folder, "add", "--", path)
    if added.returncode != 0:
        raise Refused(f"git add failed: {added.stderr.strip()}", kind="git_failed")
    files = _git(folder, "diff", "--cached", "--name-only", "--", path).stdout.split()
    if not files:
        raise Refused(f"nothing to commit in {path}/: it is as committed", kind="nothing_to_commit")
    args = ["commit", "-q", "-m", message]
    if author:
        args += ["--author", author]
    done = _git(folder, *args, "--", path)
    if done.returncode != 0:
        raise Refused(
            f"git commit failed: {(done.stderr or done.stdout).strip()}", kind="git_failed"
        )
    commit = last_commit(folder, path)
    if commit is None:  # pragma: no cover - the commit just succeeded
        raise Refused("git committed but the commit cannot be read back", kind="git_failed")
    return commit, files


def _identity(folder: Path) -> str | None:
    out = _git(folder, "config", "user.name")
    return out.stdout.strip() or None if out.returncode == 0 else None


# ------------------------------------------------------------------ folder


def _require_folder(folder: Path) -> None:
    if not (folder / "pre").is_dir():
        raise Refused(
            f"{folder} is not an experiment folder (no pre/); make one with "
            "`dobladillo experiment new`",
            kind="missing_folder",
        )


def gate(folder: Path) -> tuple[str, str | None]:
    """The gate as the working copy has it, and which file it is in."""
    plan = folder / "pre" / "plan.md"
    text = plan_criterion(plan.read_text()) if plan.is_file() else ""
    if text:
        return text, "pre/plan.md"
    prediction = folder / "pre" / "prediction.json"
    text = prediction_criterion(prediction.read_text()) if prediction.is_file() else ""
    return (text, "pre/prediction.json") if text else ("", None)


@dataclass(frozen=True)
class LockState:
    """Whether `pre/` is locked: committed, with a gate written in the commit."""

    repository: Path | None
    #: The gate as committed; "" when the committed pre/ has none.
    committed_gate: str
    #: The last commit that touched pre/.
    commit: Commit | None
    #: pre/ paths that differ from that commit.
    changed: tuple[str, ...]

    @property
    def locked(self) -> bool:
        return bool(self.committed_gate) and self.commit is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "in_git": self.repository is not None,
            "repository": None if self.repository is None else str(self.repository),
            "locked": self.locked,
            "committed_gate": self.committed_gate,
            "commit": None if self.commit is None else self.commit.as_dict(),
            "changed_since": list(self.changed),
        }


def lock_state(folder: Path) -> LockState:
    repo = repository(folder)
    if repo is None:
        return LockState(repository=None, committed_gate="", commit=None, changed=())
    committed = plan_criterion(_committed(folder, "pre/plan.md") or "")
    if not committed:
        committed = prediction_criterion(_committed(folder, "pre/prediction.json") or "")
    return LockState(
        repository=repo,
        committed_gate=committed,
        commit=last_commit(folder, "pre"),
        changed=_changed(folder, "pre"),
    )


def _locked_message(state: LockState) -> str:
    assert state.commit is not None
    return (
        f"pre/ is locked: the gate was committed in {state.commit.sha[:10]} at "
        f"{_iso(state.commit.at)}"
    )


# ------------------------------------------------------------------ the gate


def write_criterion(folder: Path, text: str) -> dict[str, Any]:
    """Write the gate into `pre/plan.md`'s `> criterion:` line. Refuses once locked."""
    _require_folder(folder)
    lines_in = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines_in and not lines_in[0]:
        lines_in.pop(0)
    while lines_in and not lines_in[-1]:
        lines_in.pop()
    if not lines_in:
        raise Refused(
            "the criterion is empty: write what result would make this a failure",
            kind="empty_criterion",
        )
    plan = folder / "pre" / "plan.md"
    if not plan.is_file():
        raise Refused("no pre/plan.md to write the gate into", kind="missing_file")
    state = lock_state(folder)
    if state.locked:
        raise Refused(
            _locked_message(state) + ". A gate changed after the lock is a new gate: say so "
            "in during/log.md, or start a new experiment",
            kind="locked",
        )

    original = plan.read_text()
    lines = original.splitlines()
    at = [i for i, line in enumerate(lines) if line.strip().startswith(CRITERION_LINE)]
    if not at:
        raise Refused(f"pre/plan.md has no `{CRITERION_LINE}` line", kind="no_gate_line")
    if len(at) > 1:
        raise Refused(
            f"pre/plan.md has {len(at)} `{CRITERION_LINE}` lines; which is the gate is "
            "ambiguous. Leave one",
            kind="ambiguous_gate",
        )
    start = end = at[0]
    end += 1
    while end < len(lines) and lines[end].strip().startswith(">"):
        end += 1
    previous = plan_criterion(original)
    quoted = [f"{CRITERION_LINE} {lines_in[0].strip()}"]
    quoted += [f"> {line}" if line.strip() else ">" for line in lines_in[1:]]
    lines[start:end] = quoted
    plan.write_text("\n".join(lines) + ("\n" if original.endswith("\n") else ""))
    return {
        "directory": str(folder),
        "file": "pre/plan.md",
        "criterion": plan_criterion(plan.read_text()),
        "previous": previous or None,
        "next": "Lock the plan (`dobladillo experiment lock`) before taking data.",
    }


# ------------------------------------------------------------------ the lock


def lock(folder: Path, *, author: str | None = None) -> dict[str, Any]:
    """Commit `pre/`, gate written, so the prediction provably predates the data."""
    from dobladillo.experiments.layout import check
    from dobladillo.provenance import raw_files

    _require_folder(folder)
    if repository(folder) is None:
        raise Refused(
            f"{folder} is not inside a git repository. The lock is a commit: its time is "
            "what makes the prediction provably older than the data, and a file's "
            "modification time proves nothing. Keep experiments in a git repository",
            kind="not_in_git",
        )
    criterion, source = gate(folder)
    if not criterion:
        raise Refused(
            "the gate is not written: pre/plan.md's `criterion:` line is empty. Write what "
            "result would make this a failure (`dobladillo experiment criterion`) first",
            kind="no_criterion",
        )
    missing = check(folder).phases[0].missing
    if missing:
        raise Refused(f"pre/ is incomplete, missing {', '.join(missing)}", kind="pre_incomplete")
    before = lock_state(folder)
    if before.commit is not None and not before.changed:
        raise Refused(
            f"pre/ is already committed ({before.commit.sha[:10]} at "
            f"{_iso(before.commit.at)}) and unchanged since",
            kind="already_locked",
        )
    commit, files = _commit(
        folder,
        "pre",
        message=f"{folder.name}: lock pre/ (pre-registration)\n\nGate: {criterion}",
        author=author,
    )
    data = raw_files(folder)
    notes = []
    if data:
        notes.append(
            f"during/raw already holds {len(data)} file(s): data predating the lock make "
            "the gate a description of them, and `experiment check` says so"
        )
    if before.locked:
        notes.append(
            f"this amends an earlier lock, {before.commit.sha[:10]}"
            if before.commit
            else "this amends an earlier lock"
        )
    return {
        "directory": str(folder),
        "locked": True,
        "criterion": criterion,
        "criterion_from": source,
        "commit": commit.as_dict(),
        "files": files,
        "notes": notes,
        "next": "Order from pre/order/, then record the instrument and take data.",
    }


# ---------------------------------------------------------------- the log


def log(folder: Path, text: str, *, author: str | None = None) -> dict[str, Any]:
    """Append a timestamped entry to `during/log.md`."""
    _require_folder(folder)
    body = text.replace("\r\n", "\n").strip()
    if not body:
        raise Refused("the entry is empty", kind="empty_entry")
    path = folder / "during" / "log.md"
    if not path.is_file():
        raise Refused("no during/log.md to append to", kind="missing_file")
    stamp = _iso(_dt.datetime.now(_dt.UTC).timestamp())
    who = author or _identity(folder)
    existing = path.read_text()
    entry = f"\n### {stamp}" + (f" — {who}" if who else "") + f"\n\n{body}\n"
    with path.open("a") as handle:
        handle.write(("" if existing.endswith("\n") or not existing else "\n") + entry)
    return {
        "directory": str(folder),
        "file": "during/log.md",
        "at": stamp,
        "author": who,
        "entry": body,
        "note": "The time is this computer's clock. It becomes evidence when during/ is committed.",
    }


# ------------------------------------------------------ the instrument record


def _finite(raw: str) -> int | float:
    try:
        value = int(raw)
    except ValueError:
        try:
            number = float(raw)
        except ValueError:
            raise ValueError(f"not a number: {raw!r}") from None
        if not math.isfinite(number):
            raise ValueError(f"not a finite number: {raw!r}") from None
        return number
    return value


def _positive(raw: str) -> int | float:
    value = _finite(raw)
    if value <= 0:
        raise ValueError(f"must be greater than 0, got {raw}")
    return value


def _non_negative(raw: str) -> int | float:
    value = _finite(raw)
    if value < 0:
        raise ValueError(f"must be 0 or more, got {raw}")
    return value


def _count(raw: str) -> int:
    value = _finite(raw)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"must be a whole number greater than 0, got {raw}")
    return value


def _ph(raw: str) -> int | float:
    value = _finite(raw)
    if not 0 < value <= 14:
        raise ValueError(f"a pH is between 0 and 14, got {raw}")
    return value


def _text(raw: str) -> str:
    return raw.strip()


def _boolean(raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered not in ("true", "false"):
        raise ValueError(f"write true or false, got {raw!r}")
    return lowered == "true"


def _one_of(name: str, options: tuple[str, ...]) -> Callable[[str], str]:
    def parse(raw: str) -> str:
        text = raw.strip()
        if text not in options:
            raise ValueError(f"{name} is one of {', '.join(options)}; got {raw!r}")
        return text

    return parse


def _imaging_order(raw: str) -> list[str]:
    text = raw.strip()
    try:
        value = json.loads(text) if text.startswith("[") else [p.strip() for p in text.split(",")]
    except ValueError:
        raise ValueError(f"not a list: {raw!r}") from None
    if not isinstance(value, list) or sorted(value) != ["X", "Y"]:
        raise ValueError(f"write X,Y or Y,X (the order the arms were imaged in), got {raw!r}")
    return [str(v) for v in value]


def _condition(name: str) -> Callable[[str], Any]:
    """A calibration condition, checked as `read_conditions` checks it."""
    from dobladillo.experiments.instrument import condition_problem

    def parse(raw: str) -> Any:
        text = raw.strip()
        value: Any
        if name == "scan.closed_loop":
            value = _boolean(text)
        elif name == "scan.direction":
            value = text
        elif text.startswith("{"):
            try:
                value = json.loads(text)
            except ValueError:
                raise ValueError(f"not a JSON object: {raw!r}") from None
        else:
            try:
                value = _finite(text)
            except ValueError:
                value = text
        why = condition_problem(name, value)
        if why is not None:
            raise ValueError(why)
        return value

    return parse


def _frame_times(raw: str) -> dict[str, list[int | float]]:
    try:
        value = json.loads(raw)
    except ValueError:
        raise ValueError(f"not a JSON object: {raw!r}") from None
    ok = isinstance(value, dict) and all(
        isinstance(k, str)
        and isinstance(v, list)
        and all(isinstance(t, int | float) and not isinstance(t, bool) for t in v)
        for k, v in value.items()
    )
    if not ok:
        raise ValueError('write {"<folder under during/raw>": [t0, t1, ...]}, times in s')
    return value  # type: ignore[no-any-return]


@dataclass(frozen=True)
class RecordField:
    """One field of `during/instrument.json`: what it means and what it accepts."""

    path: tuple[str, ...]
    meaning: str
    allowed: str
    parse: Callable[[str], Any]

    @property
    def name(self) -> str:
        return ".".join(self.path)


# fmt: off
def _fields() -> tuple[RecordField, ...]:
    from dobladillo.experiments.calibration import TIP_PART_FIELD
    from dobladillo.experiments.instrument import CALIBRATION_CONDITIONS

    # The calibration conditions state their own meaning and allowed values;
    # they are taken from there rather than said twice.
    stated = {c.name: c for c in (*CALIBRATION_CONDITIONS, TIP_PART_FIELD)}
    tip = (
        "the tip's apex radius MEASURED {}, nm. A nominal 10 nm tip is routinely 8-20 nm "
        "in use, and every width is corrected by sqrt(R): never the box's value"
    )
    above_0 = "a number greater than 0"
    at_least_0 = "a number >= 0"
    table: list[tuple[str, str, str, Callable[[str], Any]]] = [
        ("instrument", "the AFM, make and model; named in every reading's provenance",
         "text", _text),
        ("mode", "the imaging mode, e.g. tapping in air, PeakForce in liquid", "text", _text),
        ("tip.part_number", "", "", _text),
        ("tip.nominal_radius_nm", "the radius the tip was sold as, nm. Recorded, and never "
         "used in place of a measurement", above_0, _positive),
        ("tip.measured_radius_before_nm", tip.format("before the session"), above_0, _positive),
        ("tip.measured_radius_between_nm", tip.format("between the two arms (E2)"), above_0,
         _positive),
        ("tip.measured_radius_after_nm", tip.format("after the session"), above_0, _positive),
        ("imaging_order", "E2: the order the two blinded arms were imaged in, a coin flip",
         "X,Y or Y,X", _imaging_order),
        ("reference.flat_height_nm", "the median height of flat rectangles from E1, imaged "
         "the same way, nm: what 'flat' means for E2 and E9", above_0, _positive),
        ("reference.from", "which experiment and scans that height comes from", "text", _text),
        ("buffer.tris_mm", "Tris in the folding buffer, mM", at_least_0, _non_negative),
        ("buffer.edta_mm", "EDTA in the folding buffer, mM", at_least_0, _non_negative),
        ("buffer.mgcl2_mm", "MgCl2 in the folding buffer, mM. Not the deposition buffer's, "
         "which is deposition.mgcl2_mm", at_least_0, _non_negative),
        ("buffer.ph", "the folding buffer's pH", "a number, 0 to 14", _ph),
        ("temperature_c", "the temperature the images were taken at, C", "a number", _finite),
        ("scan.size_nm", "the scan's side length, nm", above_0, _positive),
        ("scan.pixels", "pixels per line", "a whole number greater than 0", _count),
        ("scan.rate_hz", "lines per second, Hz", above_0, _positive),
        ("scan.angle_deg", "", "", _condition("scan.angle_deg")),
        ("scan.direction", "", "", _condition("scan.direction")),
        ("scan.channel", "the file channel to read, as `dobladillo afm read` lists them; "
         "empty for the format's height channel", "text", _text),
        ("scan.closed_loop", "", "", _condition("scan.closed_loop")),
        ("deposition.mgcl2_mm", "", "", _condition("deposition.mgcl2_mm")),
        ("deposition.nicl2_mm", "", "", _condition("deposition.nicl2_mm")),
        ("frames.interval_s", "drift: the time between frames, s, from the instrument, not "
         "from file dates", above_0, _positive),
        ("frames.times_s", "drift: each frame's time per series, s, keyed by its folder "
         "under during/raw", '{"<folder>": [t0, t1, ...]}', _frame_times),
        ("staples.source", "where this fold's staples came from: fresh (as delivered) or "
         "recycled (recovered from an earlier fold's purification)", "fresh or recycled",
         _one_of("staples.source", ("fresh", "recycled"))),
        ("staples.pool", "recycled only: the label on the recovered pool's tube (an earlier "
         "fold's purification.kept_as)", "text", _text),
        ("staples.reuse_cycle", "recycled only: how many folds the pool has already been "
         "through; 1 = recovered once", "a whole number greater than 0", _count),
        ("staples.topped_up", "recycled only: which fresh staples were added back, and how "
         "much", "text", _text),
        ("purification.method", "how the fold was purified (common-techniques section 5)",
         "PEG precipitation, 100 kDa spin filter or other",
         _one_of("purification.method", ("PEG precipitation", "100 kDa spin filter", "other"))),
        ("purification.excess_kept", "were the excess staples kept for reuse (the PEG "
         "supernatant or the filter's flow-through) rather than discarded", "true or false",
         _boolean),
        ("purification.kept_as", "the label written on the kept tube: the pool name a later "
         "fold records in staples.pool", "text", _text),
        ("calibration_reference", "what was scanned for a calibration when the folder's part "
         "does not say: calibration-tile, or a reference JSON's path relative to the folder. "
         "Empty in a calibration-tile folder", "text", _text),
    ]
    return tuple(
        RecordField(
            tuple(name.split(".")),
            meaning or stated[name].meaning,
            allowed or stated[name].allowed,
            parse,
        )
        for name, meaning, allowed, parse in table
    )
# fmt: on


#: Fields whose every allowed value can be listed, as a form offers them.
CHOICES: Final[dict[str, tuple[str, ...]]] = {
    "scan.direction": ("trace", "retrace"),
    "scan.closed_loop": ("true", "false"),
    "imaging_order": ("X,Y", "Y,X"),
    "staples.source": ("fresh", "recycled"),
    "purification.method": ("PEG precipitation", "100 kDa spin filter", "other"),
    "purification.excess_kept": ("true", "false"),
}

#: Fields whose value is itself an object, not a group of fields.
OBJECT_FIELDS: Final = frozenset({("frames", "times_s")})


def template_fields(value: Any = None, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Every leaf of `INSTRUMENT_TEMPLATE` that holds a reading, notes left out."""
    value = INSTRUMENT_TEMPLATE if value is None else value
    out: list[tuple[str, ...]] = []
    for key, item in value.items():
        path = (*prefix, key)
        if key == "note":
            continue
        if isinstance(item, dict) and path not in OBJECT_FIELDS:
            out += template_fields(item, path)
        else:
            out.append(path)
    return out


def _lookup(data: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _instrument(folder: Path) -> tuple[Path, dict[str, Any]]:
    path = folder / "during" / "instrument.json"
    if not path.is_file():
        raise Refused("no during/instrument.json", kind="missing_file")
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        raise Refused(
            f"during/instrument.json is not valid JSON: {e}", kind="invalid_record"
        ) from e
    if not isinstance(data, dict):
        raise Refused("during/instrument.json is not a JSON object", kind="invalid_record")
    return path, data


def describe_record(folder: Path) -> dict[str, Any]:
    """Every field, its meaning, what it accepts, and what the record holds now."""
    _require_folder(folder)
    _, data = _instrument(folder)
    return {
        "directory": str(folder),
        "file": "during/instrument.json",
        "fields": [
            {
                "field": f.name,
                "meaning": f.meaning,
                "allowed": f.allowed,
                "choices": list(CHOICES.get(f.name, ())),
                "value": _lookup(data, f.path),
            }
            for f in _fields()
        ],
    }


def set_record(folder: Path, assignments: list[str]) -> dict[str, Any]:
    """Set fields of `during/instrument.json` from `key=value`; an empty value clears.

    Every assignment is validated before anything is written, so a bad one
    leaves the record exactly as it was.
    """
    _require_folder(folder)
    if not assignments:
        raise Refused("nothing to set: pass --set field=value", kind="invalid_parameters")
    fields = {f.name: f for f in _fields()}
    parsed: list[tuple[RecordField, Any]] = []
    for assignment in assignments:
        key, sep, raw = assignment.partition("=")
        key = key.strip()
        if not sep:
            raise Refused(f"{assignment!r} is not field=value", kind="invalid_parameters")
        field = fields.get(key)
        if field is None:
            raise Refused(
                f"{key!r} is not a field of during/instrument.json. Fields: " + ", ".join(fields),
                kind="unknown_field",
            )
        if not raw.strip():
            parsed.append((field, _lookup(INSTRUMENT_TEMPLATE, field.path)))
            continue
        try:
            parsed.append((field, field.parse(raw)))
        except ValueError as e:
            raise Refused(f"{key}: {e}. Allowed: {field.allowed}", kind="invalid_value") from None

    path, data = _instrument(folder)
    changed: dict[str, Any] = {}
    for field, value in parsed:
        node = data
        for key in field.path[:-1]:
            child = node.setdefault(key, {})
            if not isinstance(child, dict):
                raise Refused(
                    f"during/instrument.json: {key} is not an object", kind="invalid_record"
                )
            node = child
        old = node.get(field.path[-1])
        node[field.path[-1]] = value
        changed[field.name] = {"from": old, "to": value}
    path.write_text(json.dumps(data, indent=2) + "\n")
    return {"directory": str(folder), "file": "during/instrument.json", "changed": changed}


# ------------------------------------------------------------- raw uploads


def _raw_name(name: str) -> PurePosixPath:
    relative = PurePosixPath(name.strip())
    if (
        not name.strip()
        or "\\" in name
        or relative.is_absolute()
        or any(part in ("", ".", "..") for part in relative.parts)
        or any(part.startswith(".") for part in relative.parts)
    ):
        raise Refused(
            f"{name!r} is not a name under during/raw: use a relative path such as "
            "scan-01.spm or staircase/S1-01.spm, without .. or hidden parts",
            kind="outside_raw",
        )
    if relative.name == "README.md":
        raise Refused("README.md in during/raw is the folder's own note", kind="already_exists")
    return relative


def upload(folder: Path, source: Path, *, name: str | None = None) -> dict[str, Any]:
    """Copy a raw file into `during/raw/`, never over one, and record its hash."""
    from dobladillo.provenance import file_sha256

    _require_folder(folder)
    state = lock_state(folder)
    if not state.locked:
        raise Refused(
            "pre/ is not locked yet. A raw file that enters the record before the gate "
            "is committed makes the gate a description of it: write the gate and run "
            "`dobladillo experiment lock` first",
            kind="not_locked",
        )
    if not source.is_file():
        raise Refused(f"no file {source}", kind="missing_file")
    relative = _raw_name(name if name is not None else source.name)
    raw = (folder / "during" / "raw").resolve()
    target = (raw / relative).resolve()
    if raw not in target.parents:
        raise Refused(f"{relative} resolves outside during/raw", kind="outside_raw")
    if target.exists() or (raw / relative).is_symlink():
        raise Refused(
            f"during/raw/{relative} already exists. A raw file is never replaced: give the "
            "new one another name",
            kind="already_exists",
        )

    digest = file_sha256(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if raw not in target.parent.resolve().parents and target.parent.resolve() != raw:
        raise Refused(f"{relative} resolves outside during/raw", kind="outside_raw")
    with source.open("rb") as src, target.open("xb") as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)
    stat = source.stat()
    # The instrument's own time where the source has one; the record's
    # evidence is still the commit, and `check` says which it read.
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    if file_sha256(target) != digest:
        target.unlink()
        raise Refused(f"the copy of {source.name} does not match it", kind="copy_failed")

    size = target.stat().st_size
    stamp = _iso(_dt.datetime.now(_dt.UTC).timestamp())
    record = folder / "during" / UPLOADS
    entries: list[Any] = []
    if record.is_file():
        try:
            loaded = json.loads(record.read_text())
            entries = loaded if isinstance(loaded, list) else []
        except ValueError:
            raise Refused(f"during/{UPLOADS} is not valid JSON", kind="invalid_record") from None
    entries.append({"path": str(relative), "sha256": digest, "bytes": size, "at": stamp})
    record.write_text(json.dumps(entries, indent=2) + "\n")
    in_folder = f"during/raw/{relative}"
    ignored = bool(_ignored(folder, [in_folder])) if state.repository else False
    return {
        "directory": str(folder),
        "path": in_folder,
        "sha256": digest,
        "bytes": size,
        "recorded_in": f"during/{UPLOADS}",
        "ignored_by_git": ignored,
        "next": "Save the lab record (`dobladillo experiment commit --phase during`) so the "
        "file's time becomes evidence"
        + (
            ". git ignores this file, so its hash in during/uploads.json is its record"
            if ignored
            else ""
        ),
    }


# --------------------------------------------------------------- commits


PHASE_COMMITS: Final = ("during", "post")


def commit_phase(
    folder: Path, phase: str, *, message: str | None = None, author: str | None = None
) -> dict[str, Any]:
    """Commit `during/` or `post/`. Only after the lock, and never with pre/ changed."""
    from dobladillo.provenance import raw_files

    _require_folder(folder)
    if phase not in PHASE_COMMITS:
        raise Refused(
            f"phase must be one of {', '.join(PHASE_COMMITS)}; pre/ is committed by "
            "`experiment lock`",
            kind="invalid_phase",
        )
    state = lock_state(folder)
    if state.repository is None:
        raise Refused(f"{folder} is not inside a git repository", kind="not_in_git")
    if not state.locked:
        raise Refused(
            f"the plan (pre/) is not locked: saving {phase}/ first would put the data "
            "before the pass/fail criterion. Lock the plan first",
            kind="not_locked",
        )
    if state.changed:
        raise Refused(
            f"pre/ has changed since it was locked ({', '.join(state.changed)}). Commit "
            "that as its own act (`experiment lock`), or undo it, first",
            kind="pre_changed",
        )
    if not (folder / phase).is_dir():
        raise Refused(f"no {phase}/ in {folder}", kind="missing_file")
    text = (message or "").strip() or f"{folder.name}: {phase}/"
    commit, files = _commit(folder, phase, message=text, author=author)
    ignored: list[str] = []
    if phase == "during":
        ignored = _ignored(folder, [str(p.relative_to(folder)) for p in raw_files(folder)])
    return {
        "directory": str(folder),
        "phase": phase,
        "commit": commit.as_dict(),
        "files": files,
        "ignored_by_git": ignored,
    }


# ------------------------------------------------------------------ status


@dataclass(frozen=True)
class Analysis:
    """A command that analyses a folder of one part, and where it is described."""

    command: tuple[str, ...]
    experiment: str
    protocol: str
    writes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": " ".join(self.command),
            "experiment": self.experiment,
            "protocol": self.protocol,
            "writes": list(self.writes),
        }


_REPORT = Analysis(
    ("experiment", "report"),
    "E1",
    "experiments/protocols/E1-rectangle-afm.md",
    ("post/measurements.json", "post/comparison.json", "post/report.md"),
)
_PATTERN = Analysis(
    ("experiment", "pattern"),
    "E8",
    "experiments/protocols/E8-patterned-rectangle.md",
    ("post/pattern.json", "post/pattern.md"),
)
_CALIBRATION = (
    Analysis(
        ("calibrate", "report"),
        "K3-K8",
        "experiments/protocols/K4-tip-reconstruction.md",
        ("post/calibration.json",),
    ),
    Analysis(
        ("experiment", "pattern"),
        "K2",
        "experiments/protocols/K2-calibration-tile-fold.md",
        ("post/pattern.json", "post/pattern.md"),
    ),
)
_ARMS = Analysis(
    ("experiment", "compare-arms"),
    "E2",
    "experiments/protocols/E2-twist-pair.md",
    ("post/arms.json",),
)

#: Which analyses apply to a folder, by its part, as the protocols run them.
#: A part not listed (the hinge, E3) has no analysis command yet: its
#: protocol counts by hand.
ANALYSES: Final[dict[str, tuple[Analysis, ...]]] = {
    "rectangle": (
        _REPORT,
        Analysis(
            ("experiment", "folding-screen"),
            "E11",
            "experiments/protocols/E11-isothermal-folding.md",
            ("post/folding_screen.json",),
        ),
    ),
    "pattern": (_PATTERN,),
    "bundle": (
        Analysis(
            ("experiment", "rods"),
            "E10",
            "experiments/protocols/E10-six-helix-bundle.md",
            ("post/rods.json",),
        ),
    ),
    "twist-corrected": (_ARMS,),
    "twist-uncorrected": (_ARMS,),
    "dimer": (
        Analysis(
            ("experiment", "assembly"),
            "E9",
            "experiments/protocols/E9-rectangle-dimer.md",
            ("post/assembly.json",),
        ),
    ),
    "calibration-tile": _CALIBRATION,
    "calibration-tile-biotin": _CALIBRATION,
}


def _part(folder: Path) -> str | None:
    try:
        part = json.loads((folder / "pre" / "prediction.json").read_text()).get("part")
    except (OSError, ValueError, AttributeError):
        return None
    return part if isinstance(part, str) else None


def status(folder: Path) -> dict[str, Any]:
    """Where a folder is in its lifecycle: each step done, next or blocked, and why."""
    from dobladillo.experiments.layout import check

    _require_folder(folder)
    report = check(folder)
    lock_now = lock_state(folder)
    criterion, source = gate(folder)
    part = _part(folder)
    analyses = ANALYSES.get(part or "", ())
    chain = report.chain
    hashes = {s.name: s.sha256 for s in chain.scans} if chain is not None else {}
    raw_dir = folder / "during" / "raw"
    raw = (
        [
            {
                "path": str(p.relative_to(raw_dir)),
                "bytes": p.stat().st_size,
                "sha256": hashes.get(str(p.relative_to(folder))),
            }
            for p in sorted(raw_dir.rglob("*"))
            if p.is_file() and p.name != "README.md"
        ]
        if raw_dir.is_dir()
        else []
    )
    post_dir = folder / "post"
    post = sorted(
        str(p.relative_to(folder))
        for p in (post_dir.rglob("*") if post_dir.is_dir() else [])
        if p.is_file() and p.name != "README.md"
    )
    in_git = lock_now.repository is not None
    during_changed = _changed(folder, "during") if in_git else ()
    post_changed = _changed(folder, "post") if in_git else ()
    pre_missing = report.phases[0].missing

    steps: list[dict[str, Any]] = []

    def step(key: str, title: str, done: bool, blocked: str | None, detail: str) -> None:
        steps.append(
            {"step": key, "title": title, "done": done, "blocked": blocked, "detail": detail}
        )

    step(
        "gate",
        "Write the pass/fail criterion",
        bool(criterion),
        None,
        f"written in {source}"
        if criterion
        else "not written yet (it goes in the plan, pre/plan.md)",
    )
    order_ok = "order/" not in pre_missing
    step(
        "order",
        "Order files",
        order_ok,
        None if order_ok else "the order files are missing (pre/order/)",
        "ready to download (pre/order/)" if order_ok else "",
    )
    lock_blocked = (
        "the folder is not in a git repository"
        if not in_git
        else "write the pass/fail criterion first"
        if not criterion
        else f"the plan is missing {', '.join(pre_missing)}"
        if pre_missing
        else None
    )
    lock_done = lock_now.locked and not lock_now.changed
    step(
        "lock",
        "Lock the plan",
        lock_done,
        None if lock_done else lock_blocked,
        "committed " + lock_now.commit.sha[:10]
        if lock_done and lock_now.commit
        else "the plan changed after it was locked: " + ", ".join(lock_now.changed)
        if lock_now.locked
        else "the plan (pre/) is not locked yet",
    )
    step(
        "data",
        "Record the lab work",
        bool(raw),
        None if lock_now.locked else "lock the plan first",
        f"{len(raw)} raw file(s)" if raw else "no raw data yet (during/raw/)",
    )
    commit_done = bool(raw) and in_git and not during_changed
    step(
        "commit_during",
        "Save the lab record",
        commit_done,
        None if lock_now.locked and in_git else "lock the plan first",
        "the lab record (during/) is committed"
        if commit_done
        else f"{len(during_changed)} change(s) not committed"
        if during_changed
        else "nothing to commit yet",
    )
    analysed = any(p in post for a in analyses for p in a.writes)
    step(
        "analyse",
        "Analyse",
        analysed,
        "no analysis command for this part yet"
        if not analyses
        else None
        if raw
        else "no raw data yet",
        ", ".join(p for p in post) or "no results yet (post/)",
    )
    next_step = next((s["step"] for s in steps if not s["done"] and not s["blocked"]), None)
    for s in steps:
        s["state"] = (
            "done"
            if s["done"]
            else "blocked"
            if s["blocked"]
            else ("next" if s["step"] == next_step else "todo")
        )

    return {
        "directory": str(folder),
        "name": folder.name,
        "part": part,
        "criterion": {"text": criterion, "in": source},
        "lock": lock_now.as_dict(),
        "raw": raw,
        "post": post,
        "changed": {"during": list(during_changed), "post": list(post_changed)},
        "analyses": [a.as_dict() for a in analyses],
        "steps": steps,
        "next": next_step,
        "check": report.as_dict(),
    }

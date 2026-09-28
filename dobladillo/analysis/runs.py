"""Reading a finished run, and refusing to read one that is not a result.

This is the receipt half of the simulation gate. A bundle carries metadata
saying what it is; an analysis that ignores that metadata will happily turn a
two-thousand-step smoke test into a table of measurements, and nothing in the
numbers themselves gives it away.

So the rule is the one from the pipeline proposal, enforced rather than
remembered: **nothing downstream reads a raw result.** A run is checked before
it is analysed, and a check that fails is an exception, not a warning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad

if TYPE_CHECKING:
    from dobladillo.analysis.trajectory import Frame

#: Stage inputs a complete run must have produced a final configuration for.
STAGES = ("01_mc", "02_md_trapped", "03_md_released", "04_production")


def production_trajectory(directory: Path) -> Path:
    """The trajectory a run's observables are measured on. Named once, here,
    because the frames and the fluctuation are read from it separately and
    must be read from the same file."""
    return directory / "traj_04_production.dat"


class NotAResult(Exception):
    """Raised when a run exists but must not be treated as a measurement."""


@dataclass(frozen=True)
class RunCheck:
    directory: Path
    problems: tuple[str, ...]
    metadata: dict[str, Any]

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "ok": self.ok,
            "problems": list(self.problems),
            "conditions": self.metadata.get("model", {}),
            "steps": self.metadata.get("steps", {}),
            "design_sha256": (self.metadata.get("provenance") or {}).get("design_sha256"),
        }


def check_run(directory: Path, *, allow_test_mode: bool = False) -> RunCheck:
    """Is this directory a finished run whose numbers mean something?

    Four things are checked, and each of them failed for real at some point
    while this was being built:

    - the metadata exists and the run is not a smoke test;
    - every stage produced its final configuration, because stages 1 to 3
      finishing says nothing at all about stage 4;
    - the topology is still the design's, so the trajectory being analysed
      belongs to the structure it claims to;
    - the trajectory is not empty.
    """
    problems: list[str] = []

    meta_path = directory / "metadata.json"
    if not meta_path.is_file():
        return RunCheck(directory, ("no metadata.json: not a bundle this toolchain made",), {})
    metadata = json.loads(meta_path.read_text())

    backend = (metadata.get("backend") or {}).get("name")
    if backend == "Metal":
        from dobladillo.sim.jobs import METAL_VALIDATION

        if METAL_VALIDATION is None:
            problems.append(
                "run on the Metal backend, which has not passed its validation against "
                "the CPU backend (sim.jobs.METAL_VALIDATION): not a result yet"
            )
    if metadata.get("test_mode") and not allow_test_mode:
        problems.append("this is a test-mode bundle; its trajectory is a smoke test, not a result")

    for stage in STAGES:
        if not (directory / f"conf_{stage}.dat").is_file():
            problems.append(f"stage {stage} produced no final configuration")

    topology = directory / f"{metadata.get('design_name', '')}.top"
    if not topology.is_file():
        problems.append("topology file missing")
    else:
        counted = len(ad.topology_bases(topology))
        expected = metadata.get("nucleotides")
        if expected is not None and counted != expected:
            problems.append(
                f"topology has {counted} nucleotides, metadata says {expected}: "
                "this trajectory is not of the design it claims to be"
            )

    # A bundle written since the provenance chain existed records its
    # topology's hash. An older one does not, and that is not a problem with
    # the run -- it predates the record -- so only a mismatch is reported.
    recorded = (metadata.get("provenance") or {}).get("files", {}).get("topology")
    if recorded and topology.is_file():
        from dobladillo.provenance import file_sha256

        if file_sha256(topology) != recorded:
            problems.append(
                "topology file changed since the bundle was written: this trajectory "
                "cannot be tied to the design the metadata names"
            )

    trajectory = production_trajectory(directory)
    if not trajectory.is_file():
        problems.append("no production trajectory")
    elif trajectory.stat().st_size == 0:
        problems.append("production trajectory is empty")

    return RunCheck(directory, tuple(problems), metadata)


def load_run(
    directory: Path, *, skip: int = 0, allow_test_mode: bool = False
) -> tuple[list[Frame], RunCheck]:
    """Frames from a run that passed its check. Raises if it did not."""
    from dobladillo.analysis.trajectory import read_trajectory

    check = check_run(directory, allow_test_mode=allow_test_mode)
    if not check.ok:
        raise NotAResult("; ".join(check.problems))
    return read_trajectory(production_trajectory(directory), skip=skip), check

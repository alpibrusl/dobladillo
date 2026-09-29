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


#: Potential energy per nucleotide, oxDNA units, that a folded structure can
#: have. Relaxed origami sits near -1.5 (the bundles here: -1.49 to -1.53);
#: anything outside this range is a structure that has come apart.
PHYSICAL_ENERGY_RANGE: tuple[float, float] = (-3.0, 1.0)

#: A designed pair counts as broken when its two nucleotides sit further apart
#: than this. Paired, they sit ~1.02 nm apart (the traps' r0 = 1.2 oxDNA units;
#: measured medians 1.02-1.03 nm in every bundle run).
BROKEN_PAIR_NM: float = 1.5

#: Fraction of designed pairs that may be broken at the end of production.
#: Chosen from three runs, not derived: the straight 6HB loses under 0.1%, the
#: deletion-strained 6HB on the CPU 6.7%, and the same design on Metal with
#: light damping 31% -- a structure a third unzipped whose energy still looked
#: physical. So the energy check alone cannot see this failure.
MAX_BROKEN_PAIR_FRACTION: float = 0.10


def designed_pairs(traps: Path) -> list[tuple[int, int]]:
    """The designed base pairs, read back from the stage-2 trap file."""
    pairs: set[tuple[int, int]] = set()
    particle: int | None = None
    for line in traps.read_text().splitlines():
        key, _, value = (part.strip() for part in line.partition("="))
        if key == "particle":
            particle = int(value)
        elif key == "ref_particle" and particle is not None:
            ref = int(value)
            pairs.add((min(particle, ref), max(particle, ref)))
            particle = None
    return sorted(pairs)


def broken_pair_fraction(configuration: Path, traps: Path) -> float | None:
    """Fraction of designed pairs pulled apart in one configuration file, or
    None when the file holds no configuration."""
    import numpy as np

    from dobladillo.analysis.trajectory import read_frames

    pairs = np.array(designed_pairs(traps))
    if not len(pairs):
        return 0.0
    frame = next(iter(read_frames(configuration)), None)
    if frame is None:
        return None
    positions = frame.positions_nm
    gaps = np.linalg.norm(positions[pairs[:, 0]] - positions[pairs[:, 1]], axis=1)
    return float((gaps > BROKEN_PAIR_NM).mean())


def check_run(directory: Path, *, allow_test_mode: bool = False) -> RunCheck:
    """Is this directory a finished run whose numbers mean something?

    Four things are checked, and each of them failed for real at some point
    while this was being built:

    - the metadata exists and the run is not a smoke test;
    - every stage produced its final configuration, because stages 1 to 3
      finishing says nothing at all about stage 4;
    - the topology is still the design's, so the trajectory being analysed
      belongs to the structure it claims to;
    - the trajectory is not empty;
    - the production energy stayed physical. The Metal backend has no check
      on bonded distances: a run that breaks the structure keeps integrating
      and exits as a success, with energies near 1e18. The CPU backend aborts
      in the same situation. So a run is refused if any recorded potential
      energy is non-finite or outside PHYSICAL_ENERGY_RANGE;
    - the structure is still paired. A run can come a third unzipped with a
      physical-looking energy, so the final configuration's designed pairs
      (from the trap file) are measured against MAX_BROKEN_PAIR_FRACTION.
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

    energy_file = directory / "energy_traj_04_production.dat"
    if energy_file.is_file():
        low, high = PHYSICAL_ENERGY_RANGE
        for line in energy_file.read_text().splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            try:
                potential = float(fields[1])
            except ValueError:
                continue
            if not (low <= potential <= high):  # also catches nan and inf
                problems.append(
                    f"production potential energy reached {potential:g} per nucleotide at "
                    f"time {fields[0]} (physical: {low} to {high}): the run blew up, and "
                    "nothing after that point is a structure"
                )
                break

    final = directory / "conf_04_production.dat"
    traps = directory / "traps.txt"
    if final.is_file() and traps.is_file():
        broken = broken_pair_fraction(final, traps)
        if broken is not None and broken > MAX_BROKEN_PAIR_FRACTION:
            problems.append(
                f"{broken:.0%} of the designed base pairs are broken at the end of production "
                f"(limit {MAX_BROKEN_PAIR_FRACTION:.0%}): the structure has partly come apart, "
                "and its shape is not the design's"
            )

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

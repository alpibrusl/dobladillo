"""Reading oxDNA trajectories, without oxDNA.

The format is simple enough to parse directly, and doing so keeps the analysis
runnable anywhere a result file lands rather than only on a machine with the
simulator installed. Each frame is three header lines followed by one line per
nucleotide:

    t = <step>
    b = <box x> <box y> <box z>
    E = <total> <potential> <kinetic>
    rx ry rz  bx by bz  nx ny nz  vx vy vz  Lx Ly Lz

Positions come out in oxDNA length units and are converted once, here, to
nanometres. Everything downstream works in nm.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from dobladilo.units import oxdna_to_nm

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Columns per nucleotide line: position, backbone-base vector, normal,
#: velocity, angular velocity.
FIELDS_PER_NUCLEOTIDE = 15


@dataclass(frozen=True)
class Frame:
    """One configuration, with positions already in nanometres."""

    step: int
    box_nm: np.ndarray
    energy: tuple[float, float, float]
    positions_nm: np.ndarray
    base_vectors: np.ndarray
    normals: np.ndarray

    @property
    def nucleotides(self) -> int:
        return len(self.positions_nm)


def _parse_frame(
    step: int, box: np.ndarray, energy: tuple[float, float, float], rows: list[str]
) -> Frame:
    flat = np.fromstring(" ".join(rows), sep=" ")
    if flat.size % FIELDS_PER_NUCLEOTIDE:
        raise ValueError(
            f"frame at step {step}: {flat.size} numbers is not a multiple of "
            f"{FIELDS_PER_NUCLEOTIDE} per nucleotide"
        )
    data = flat.reshape(-1, FIELDS_PER_NUCLEOTIDE)
    return Frame(
        step=step,
        box_nm=box,
        energy=energy,
        positions_nm=oxdna_to_nm(data[:, 0:3]),
        base_vectors=data[:, 3:6],
        normals=data[:, 6:9],
    )


def read_frames(path: Path) -> Iterator[Frame]:
    """Yield frames one at a time, so a long trajectory need not fit in memory."""
    step: int | None = None
    box: np.ndarray = np.zeros(3)
    energy = (0.0, 0.0, 0.0)
    rows: list[str] = []

    with path.open() as handle:
        for line in handle:
            if line.startswith("t ="):
                if step is not None:
                    yield _parse_frame(step, box, energy, rows)
                    rows = []
                step = int(float(line.split("=")[1]))
            elif line.startswith("b ="):
                box = oxdna_to_nm(np.fromstring(line.split("=")[1], sep=" "))
            elif line.startswith("E ="):
                values = np.fromstring(line.split("=")[1], sep=" ")
                energy = (float(values[0]), float(values[1]), float(values[2]))
            elif line.strip():
                rows.append(line)

    if step is not None:
        yield _parse_frame(step, box, energy, rows)


def read_trajectory(path: Path, *, skip: int = 0) -> list[Frame]:
    """All frames, optionally discarding the first `skip` as equilibration.

    Discarding is the caller's decision and is recorded in the report: a mean
    taken over frames that include the structure still settling is not a mean
    of the equilibrated object, and the difference is not visible in the number
    itself.
    """
    frames = list(read_frames(path))
    if skip >= len(frames):
        raise ValueError(f"asked to skip {skip} of {len(frames)} frames, leaving none")
    return frames[skip:]

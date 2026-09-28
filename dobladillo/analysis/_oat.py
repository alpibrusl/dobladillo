"""Adapter to oxDNA_analysis_tools (oat): superposition, mean structure, RMSF.

Why a dependency rather than our own. Superimposing frames is a commodity,
and this project wrote its own Kabsch and got the row/column transpose wrong:
a valid rotation matrix that turned the wrong way, visible only as an RMSF far
too large for a rigid body that merely tumbles. oat is the analysis package
that ships with oxDNA itself, and what it computes -- `svd_align`, `mean`,
`deviations` -- is what the field quotes. docs/VISION.md s3: replace the
commodity, keep only what nobody else does. What stays ours is in
`observables`: principal extents, planarity, straightness, reach, and the
sampling guard.

Every call into oat goes through this module, for the reason
`dobladillo/_scadnano.py` exists: when oat's API drifts, there is one place
to absorb it. Four things about oat as installed (v3.7.0 of the oxDNA repo,
read from its source, not remembered) shape what this module does:

* `describe` writes an index file, `<trajectory>.pyidx`, NEXT TO the
  trajectory. Run directories are results; nothing that reads them should
  write into them, and some are read-only. So oat is shown a symbolic link in
  a temporary directory and the index lands, and dies, there.
* `mean` and `deviations` hand their chunks to `oat_multiprocesser`, which
  always starts a `multiprocessing.Pool`, even for one CPU, and prints
  progress to stdout. A pool under the spawn start method (macOS's default)
  re-imports the caller's main module, and a caller without a main guard --
  `python -`, a notebook cell -- hangs forever; the stdout progress would
  corrupt `--json` output. So the pool is swapped, for the duration of the
  call only, for a serial loop that honours the same documented contract:
  call `function(ctx, chunk_size, i)` for each chunk and pass the result to
  `callback(i, result)`. The numerics are untouched; this changes who runs
  the chunks, not what they compute.
* `mean` picks a RANDOM reference frame when given none. The first frame is
  passed explicitly, so the answer is a function of the trajectory and not of
  a seed nobody recorded.
* oat converts oxDNA length units to nm inside `deviations`, with its own
  0.8518. `dobladillo.units` is meant to be the only place a unit is
  converted, so the two are held equal by a test rather than trusted to be.
"""

from __future__ import annotations

import math
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from dobladillo.units import oxdna_to_nm

#: What oat multiplies squared-deviation roots by in `deviations` to report
#: nm. Restated here so a test can hold it to `units.OXDNA_LENGTH_UNIT_NM`.
OAT_LENGTH_UNIT_NM = 0.8518


@dataclass(frozen=True)
class Deviations:
    """oat's mean structure of a trajectory, and each nucleotide's deviation
    from it.

    `rmsf_nm` is per nucleotide, over frames; `rmsd_nm` is per frame, over
    nucleotides. The mean structure is centred on the origin and in nm.
    """

    mean_structure_nm: np.ndarray
    rmsf_nm: np.ndarray
    rmsd_nm: np.ndarray
    frames: int
    nucleotides: int


def provenance() -> str:
    """Which oat computed a number, for the report's metadata."""
    from importlib.metadata import version

    return f"oxDNA_analysis_tools {version('oxDNA-analysis-tools')}: mean + deviations"


def _quiet() -> None:
    from oxDNA_analysis_tools.UTILS.logger import logger_settings

    # oat's INFO lines go to stderr; warnings still do.
    logger_settings.set_quiet(True)


def _serial(
    nconfs: int,
    ncpus: int,
    function: Callable[[Any, int, int], Any],
    callback: Callable[[int, Any], None],
    ctx: Any,
) -> None:
    """`oat_multiprocesser`'s contract, run in this process. See the module
    docstring for why the pool is not used."""
    from oxDNA_analysis_tools.UTILS.oat_multiprocesser import get_chunk_size

    del ncpus  # one process, whatever was asked
    chunk_size = get_chunk_size()
    for i in range(math.ceil(nconfs / chunk_size)):
        callback(i, function(ctx, chunk_size, i))


@contextmanager
def _in_process() -> Iterator[None]:
    """Swap the pool for `_serial` in the two oat modules used, and put it
    back afterwards however the call ends. Each module bound the name at
    import, so it is replaced where it is looked up, not where it is defined."""
    import oxDNA_analysis_tools.deviations as oat_deviations
    import oxDNA_analysis_tools.mean as oat_mean

    modules = (oat_mean, oat_deviations)
    saved = [module.oat_multiprocesser for module in modules]
    for module in modules:
        module.oat_multiprocesser = _serial
    try:
        yield
    finally:
        for module, original in zip(modules, saved, strict=True):
            module.oat_multiprocesser = original


def deviations(trajectory: Path, *, skip: int = 0) -> Deviations:
    """Mean structure and RMSF of a trajectory file, computed by oat.

    oat's own pipeline, `oat mean -d`: every frame after `skip` is superimposed
    on the first of them and averaged, then every frame is superimposed on
    that average and its deviation measured. The first frame is the reference
    rather than a random one; see the module docstring.

    `skip` discards frames as equilibration, the same frames
    `trajectory.read_trajectory(skip=...)` would.
    """
    from oxDNA_analysis_tools.deviations import deviations as oat_deviations
    from oxDNA_analysis_tools.mean import mean as oat_mean
    from oxDNA_analysis_tools.UTILS.data_structures import TrajInfo
    from oxDNA_analysis_tools.UTILS.RyeReader import describe, get_confs, inbox

    _quiet()
    trajectory = Path(trajectory).resolve()
    if not trajectory.is_file():
        raise FileNotFoundError(trajectory)

    with tempfile.TemporaryDirectory(prefix="dobladillo-oat-") as scratch:
        link = Path(scratch) / trajectory.name
        link.symlink_to(trajectory)
        top_info, traj_info = describe(None, str(link))
        if skip < 0 or skip >= traj_info.nconfs:
            raise ValueError(f"asked to skip {skip} of {traj_info.nconfs} frames, leaving none")
        # Skipping by slicing oat's frame index: `get_confs` addresses frames
        # by position in that list, so the slice is the trajectory without its
        # first `skip` frames.
        kept = TrajInfo(
            traj_info.path, traj_info.nconfs - skip, traj_info.idxs[skip:], traj_info.incl_v
        )
        reference = inbox(get_confs(top_info, kept, 0, 1)[0])
        with _in_process():
            mean_conf = oat_mean(kept, top_info, ref_conf=reference, ncpus=1)
            rmsd, rmsf = oat_deviations(kept, top_info, mean_conf, ncpus=1)

    positions = np.asarray(mean_conf.positions, dtype=float)
    return Deviations(
        mean_structure_nm=oxdna_to_nm(positions - positions.mean(axis=0)),
        rmsf_nm=np.asarray(rmsf, dtype=float),
        rmsd_nm=np.asarray(rmsd, dtype=float),
        frames=kept.nconfs,
        nucleotides=top_info.nbases,
    )


def superpose(mobile: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """`mobile` rotated and translated onto `reference`, by oat's `svd_align`.

    Both are (n, 3) arrays of the same particles in the same order, in any one
    length unit -- a rotation does not care which. The result is centred where
    the reference is centred.

    oat's function takes positions together with the two orientation vectors
    per nucleotide and rotates all three. Only positions are asked of it here,
    so the orientations go in as zeros and are dropped; they do not enter the
    fit. It also recentres its input array in place, hence the copy.
    """
    from oxDNA_analysis_tools.align import svd_align

    mobile = np.asarray(mobile, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if mobile.shape != reference.shape or mobile.ndim != 2 or mobile.shape[1] != 3:
        raise ValueError(
            f"superposition needs two (n, 3) arrays of the same particles; "
            f"got {mobile.shape} and {reference.shape}"
        )
    centre = reference.mean(axis=0)
    coords = np.stack([mobile.copy(), np.zeros_like(mobile), np.zeros_like(mobile)])
    aligned, _, _ = svd_align(
        reference - centre, coords, np.arange(len(mobile)), ref_center=np.zeros(3)
    )
    return np.asarray(aligned, dtype=float) + centre

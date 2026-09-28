"""A self-contained oxDNA job bundle: everything a run needs, in one directory.

The point of a bundle is that the machine running it needs nothing from here.
Topology, starting configuration, an input file per relaxation stage, the
external forces, a run script and a metadata file all sit together, so the
directory can be copied to a GPU box and started.

The relaxation follows oxDNA's own documented procedure, which differs from the
four steps DESIGN.md section 3 describes, and the difference is recorded rather
than smoothed over. The design document calls stage one "energy minimisation";
oxDNA has no such sim_type -- its documented first stage is Monte Carlo with
capped backbone forces, which does the same job of resolving overlaps that need
only small displacements. The stages here are MC, then MD holding the base
pairs with mutual traps, then the same MD with the traps released, then
production.

Nothing here runs anything. Producing a bundle is not evidence that a
simulation happened; the metadata says what is still owed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from dobladillo import _scadnano as ad
from dobladillo.constants import OXDNA_NA_PROXY_M
from dobladillo.units import OXDNA_LENGTH_UNIT_NM

if TYPE_CHECKING:
    import scadnano as sc

#: Backbone force caps for the relaxation stages, from oxDNA's relaxation
#: guide. They stop a badly placed nucleotide from being flung across the box.
MAX_BACKBONE_FORCE = 5.0
MAX_BACKBONE_FORCE_FAR = 10.0

#: Mutual trap stiffness and equilibrium separation, in oxDNA units. r0 = 1.2
#: is roughly the distance between paired bases.
TRAP_STIFF = 1.0
TRAP_R0 = 1.2

#: Folding and imaging happen near room temperature; production runs there.
DEFAULT_TEMPERATURE = "20C"

#: Configurations to write per relaxation stage. A configuration of a
#: 14k-nucleotide structure is about 4 MB, and oxDNA aborts a run that sustains
#: more than 1 MB/s of output. Printing "every steps/10" tripped that guard on
#: the short test stages: ten snapshots of a fast-running stage is a torrent.
#: Keeping the COUNT fixed rather than the interval makes the output rate fall
#: as stages get longer, which is the right way round.
#:
#: Relaxation only needs enough snapshots to see that it worked, so four is
#: plenty. Production is different and must not use this -- see below.
CHECKPOINTS_PER_RELAXATION_STAGE = 4

#: Production is the sampling stage, and a fixed count of four would make every
#: observable downstream a four-sample statistic: an RMSF from four frames has
#: a standard error near 40% and `analysis.observables` will report it without
#: complaint. So production fixes the STEPS PER SAMPLE instead, which scales
#: with run length in the direction that matters -- a longer run yields more
#: samples rather than rarer ones -- and is bounded at both ends so a short
#: test stage still cannot flood the output guard.
PRODUCTION_STEPS_PER_SAMPLE = 5_000
MIN_PRODUCTION_SAMPLES = 4
MAX_PRODUCTION_SAMPLES = 400

#: Energy lines are a few dozen bytes, so they can be frequent enough to plot.
ENERGY_POINTS_PER_STAGE = 100

#: Trapped MD steps needed before production will accept the structure.
#: Measured, not chosen: at 1000 steps production refuses the six-helix bundle
#: with "Distance between bonded neighbors ... exceeds acceptable values", and
#: at 20000 that error is gone. The real run uses far more; this is the floor
#: below which a bundle cannot even start its production stage.
MIN_RELAX_STEPS = 20_000


@dataclass(frozen=True)
class Stage:
    name: str
    options: dict[str, Any]
    comment: str

    def render(self) -> str:
        lines = [f"# {self.comment}", ""]
        lines += [f"{k} = {v}" for k, v in self.options.items()]
        return "\n".join(lines) + "\n"


def check_sequences_pair(design: sc.Design) -> None:
    """Refuse a design whose staples do not complement its scaffold.

    Found by losing a run: deletions added to a design AFTER its scaffold
    sequence was assigned shift every later base, and nothing complains. The
    oxDNA run starts, traps only the pairs that still happen to match (1754 of
    ~6900), and the structure comes apart over 19 hours. Geometry says which
    positions are paired; sequence must agree at every one of them.
    """
    geometric = sum(len(v) for v in design.base_pairs(allow_mismatches=True).values())
    complementary = sum(len(v) for v in design.base_pairs().values())
    if complementary < geometric:
        raise ValueError(
            f"only {complementary} of {geometric} paired positions have complementary "
            "sequences; was a deletion or insertion added after the scaffold sequence was "
            "assigned? Assign it again, last"
        )


def mutual_traps(design: sc.Design) -> tuple[str, int]:
    """An external forces file holding every base pair together.

    Two blocks per pair, not one. oxDNA's reference particle feels no force, so
    a trap defined in one direction pulls one nucleotide towards a partner that
    is free to drift away from it; the coupling is only mutual if both
    directions are written.
    """
    index = ad.nucleotide_indices(design)
    blocks: list[str] = []
    pairs = 0
    for helix, offsets in design.base_pairs().items():
        for offset in offsets:
            a = index.get((helix, offset, True))
            b = index.get((helix, offset, False))
            if a is None or b is None:
                continue
            pairs += 1
            for particle, reference in ((a, b), (b, a)):
                blocks.append(
                    "{\n"
                    "type = mutual_trap\n"
                    f"particle = {particle}\n"
                    f"ref_particle = {reference}\n"
                    f"stiff = {TRAP_STIFF}\n"
                    f"r0 = {TRAP_R0}\n"
                    "PBC = 1\n"
                    "}\n"
                )
    return "\n".join(blocks), pairs


#: The Apple-GPU backend: oxDNA PR #224 (lorenzo-rovigatti/oxDNA), kept on
#: the maintainer's advice as a separate branch -- here alpibrupa/oxDNA,
#: branch `metal-backend`, pinned at this commit. Apple GPUs have no hardware
#: double; `mixed` is the fork's software double-float, which matched the CPU
#: backend to ~2e-6 in energy on its own example.
METAL_FORK: Final = "alpibrupa/oxDNA@metal-backend"
METAL_COMMIT: Final = "6f73a293504f6cea99c3d1a119982a4dfba13273"
METAL_SETTINGS: Final = {
    "backend_precision": "mixed",
    "Metal_avoid_cpu_calculations": 1,
    "Metal_list": "verlet",
    # oxDNA aborts above 1 MB/s of output by default. At 0.1-0.3 ms/step the
    # GPU writes a 4 MB configuration every second or two, and the first
    # validation run lost its production stage to that guard after 56 frames.
    "max_io": 100,
}

#: The Metal backend implements the Brownian (`john`) thermostat and not
#: `bussi`. The thermostat sets the dynamics, not the equilibrium, so shape
#: observables are comparable -- which is exactly what the validation run
#: checks rather than assumes (see METAL_VALIDATION).
METAL_THERMOSTAT: Final = {"thermostat": "john", "diff_coeff": 2.5}

#: Evidence that Metal runs reproduce CPU runs, or None. `analysis.runs.check_run`
#: refuses a Metal run while this is None: a 143,000-line unreviewed fork does
#: not get to produce results on its word.
METAL_VALIDATION: Final[str | None] = None


def _on_metal(settings: dict[str, Any]) -> dict[str, Any]:
    """An MD stage's settings, moved to the Metal backend."""
    out = {k: v for k, v in settings.items() if k not in ("thermostat", "bussi_tau")}
    out.update(METAL_SETTINGS)
    out.update(METAL_THERMOSTAT)
    return out


def _interval(steps: int, points: int) -> int:
    """How often to print so that roughly `points` are written in `steps`."""
    return max(1, steps // max(1, points))


def _production_samples(steps: int) -> int:
    """How many configurations a production run of this length should write."""
    wanted = steps // PRODUCTION_STEPS_PER_SAMPLE
    return max(MIN_PRODUCTION_SAMPLES, min(MAX_PRODUCTION_SAMPLES, wanted))


def _common(
    *, name: str, conf_in: str, conf_out: str, trajectory: str, salt_m: float, temperature: str
) -> dict[str, Any]:
    return {
        "interaction_type": "DNA2",
        # Mandatory for DNA2, and the reason it is mandatory matters here:
        # oxDNA2 has no explicit Mg2+, so this is a monovalent proxy and every
        # result must carry it. See the metadata file.
        "salt_concentration": salt_m,
        "T": temperature,
        "topology": f"{name}.top",
        "conf_file": conf_in,
        "lastconf_file": conf_out,
        "trajectory_file": trajectory,
        "energy_file": f"energy_{Path(trajectory).stem}.dat",
        "time_scale": "linear",
        "restart_step_counter": 1,
        "verlet_skin": 0.2,
    }


def stages(
    *,
    name: str,
    steps_mc: int,
    steps_relax: int,
    steps_production: int,
    salt_m: float,
    temperature: str,
    backend: str,
) -> list[Stage]:
    """The four stages, in the order they must run.

    On `backend="Metal"` the three MD stages move to the Apple GPU; the Monte
    Carlo stage stays on the CPU, as it does for CUDA (and the Metal backend
    has no MC).
    """
    chain = [
        Stage(
            "01_mc",
            {
                "backend": "CPU",  # the guide is explicit that this stage is CPU
                "sim_type": "MC",
                "ensemble": "NVT",
                "delta_translation": 0.1,
                "delta_rotation": 0.1,
                "steps": steps_mc,
                "max_backbone_force": MAX_BACKBONE_FORCE,
                "max_backbone_force_far": MAX_BACKBONE_FORCE_FAR,
                "external_forces": 0,
                "print_conf_interval": _interval(steps_mc, CHECKPOINTS_PER_RELAXATION_STAGE),
                "print_energy_every": _interval(steps_mc, ENERGY_POINTS_PER_STAGE),
                **_common(
                    name=name,
                    conf_in=f"{name}.dat",
                    conf_out="conf_01_mc.dat",
                    trajectory="traj_01_mc.dat",
                    salt_m=salt_m,
                    temperature=temperature,
                ),
            },
            "Stage 1: Monte Carlo, resolving overlaps that need only small moves. "
            "DESIGN.md calls this energy minimisation; oxDNA has no such sim_type "
            "and its documented equivalent is this.",
        ),
        Stage(
            "02_md_trapped",
            {
                "backend": backend,
                "sim_type": "MD",
                "dt": 0.002,
                "thermostat": "bussi",
                "bussi_tau": 1000,
                "newtonian_steps": 53,
                "steps": steps_relax,
                "max_backbone_force": MAX_BACKBONE_FORCE,
                "max_backbone_force_far": MAX_BACKBONE_FORCE_FAR,
                "external_forces": 1,
                "external_forces_file": "traps.txt",
                "refresh_vel": 1,
                "print_conf_interval": _interval(steps_relax, CHECKPOINTS_PER_RELAXATION_STAGE),
                "print_energy_every": _interval(steps_relax, ENERGY_POINTS_PER_STAGE),
                **_common(
                    name=name,
                    conf_in="conf_01_mc.dat",
                    conf_out="conf_02_md_trapped.dat",
                    trajectory="traj_02_md_trapped.dat",
                    salt_m=salt_m,
                    temperature=temperature,
                ),
            },
            "Stage 2: MD with every base pair held by a mutual trap, so large "
            "displacements can relax without the structure coming unpaired.",
        ),
        Stage(
            "03_md_released",
            {
                "backend": backend,
                "sim_type": "MD",
                "dt": 0.002,
                "thermostat": "bussi",
                "bussi_tau": 1000,
                "newtonian_steps": 53,
                "steps": steps_relax,
                "max_backbone_force": MAX_BACKBONE_FORCE,
                "max_backbone_force_far": MAX_BACKBONE_FORCE_FAR,
                "external_forces": 0,
                "refresh_vel": 1,
                "print_conf_interval": _interval(steps_relax, CHECKPOINTS_PER_RELAXATION_STAGE),
                "print_energy_every": _interval(steps_relax, ENERGY_POINTS_PER_STAGE),
                **_common(
                    name=name,
                    conf_in="conf_02_md_trapped.dat",
                    conf_out="conf_03_md_released.dat",
                    trajectory="traj_03_md_released.dat",
                    salt_m=salt_m,
                    temperature=temperature,
                ),
            },
            "Stage 3: the traps released, force caps still on. If the structure "
            "is going to fall apart, it does so here rather than in production.",
        ),
        Stage(
            "04_production",
            {
                "backend": backend,
                "sim_type": "MD",
                "dt": 0.003,
                "thermostat": "bussi",
                "bussi_tau": 1000,
                "newtonian_steps": 53,
                "steps": steps_production,
                "external_forces": 0,
                "refresh_vel": 1,
                "print_conf_interval": _interval(
                    steps_production, _production_samples(steps_production)
                ),
                "print_energy_every": _interval(steps_production, ENERGY_POINTS_PER_STAGE),
                **_common(
                    name=name,
                    conf_in="conf_03_md_released.dat",
                    conf_out="conf_04_production.dat",
                    trajectory="traj_04_production.dat",
                    salt_m=salt_m,
                    temperature=temperature,
                ),
            },
            "Stage 4: production. No force caps: this is the trajectory that "
            "gets analysed, so nothing artificial should be acting on it.",
        ),
    ]
    if backend == "Metal":
        chain = [
            Stage(st.name, _on_metal(st.options) if st.name != "01_mc" else st.options, st.comment)
            for st in chain
        ]
    return chain


RUN_SCRIPT = """#!/bin/sh
# Run the stages in order, stopping at the first failure.
#
# Each stage starts from the previous stage's last configuration, so running
# them out of order, or skipping one, silently analyses something other than
# what the protocol describes.
set -eu

OXDNA=${OXDNA:-oxDNA}
command -v "$OXDNA" >/dev/null || {
    echo "oxDNA not found. Set OXDNA to its path." >&2
    exit 127
}

for stage in 01_mc 02_md_trapped 03_md_released 04_production; do
    echo "=== $stage ==="
    "$OXDNA" "input_$stage" || { echo "stage $stage failed" >&2; exit 1; }
done
echo "all stages finished"
"""


@dataclass(frozen=True)
class JobBundle:
    directory: Path
    files: dict[str, Path]
    nucleotides: int
    trapped_pairs: int
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "files": {k: str(v) for k, v in self.files.items()},
            "nucleotides": self.nucleotides,
            "trapped_pairs": self.trapped_pairs,
            "metadata": self.metadata,
        }


def write_job_bundle(
    design: sc.Design,
    *,
    directory: Path,
    name: str,
    part: str,
    backend: str = "CUDA",
    test_mode: bool = False,
    steps_override: dict[str, int] | None = None,
    salt_m: float = OXDNA_NA_PROXY_M[0],
    temperature: str = DEFAULT_TEMPERATURE,
) -> JobBundle:
    """Write the bundle. Runs nothing.

    `test_mode` shortens every stage so the whole chain can be exercised on a
    CPU in minutes. It is for proving the bundle is well formed, never for
    producing a trajectory to analyse, and the metadata says so.

    `steps_override` sets the stage lengths explicitly, for the case neither
    default covers: a run long enough to analyse but short enough to finish on
    a CPU overnight. A bundle built this way is a real run and its metadata
    does not claim otherwise, but it says how long it was, because "short" is
    a property a reader of the results needs.
    """
    if backend not in {"CPU", "CUDA", "Metal"}:
        raise ValueError(f"backend must be CPU, CUDA or Metal, got {backend!r}")
    check_sequences_pair(design)

    directory.mkdir(parents=True, exist_ok=True)
    files = ad.write_oxdna_files(design, directory=directory, name=name)

    traps_text, pairs = mutual_traps(design)
    traps = directory / "traps.txt"
    traps.write_text(traps_text)
    files["traps"] = traps

    # Test mode is short everywhere EXCEPT the trapped relaxation, which has a
    # measured floor: below it production refuses to start at all, so a
    # "shorter" test would only ever prove that it fails.
    steps = (
        {"steps_mc": 1000, "steps_relax": MIN_RELAX_STEPS, "steps_production": 2000}
        if test_mode
        else {"steps_mc": 1000, "steps_relax": 1_000_000, "steps_production": 100_000_000}
    )
    if steps_override:
        unknown = set(steps_override) - set(steps)
        if unknown:
            raise ValueError(f"unknown stage(s): {', '.join(sorted(unknown))}")
        if steps_override.get("steps_relax", MIN_RELAX_STEPS) < MIN_RELAX_STEPS:
            raise ValueError(
                f"steps_relax below the measured floor of {MIN_RELAX_STEPS}; "
                "production will refuse to start on the result"
            )
        steps = {**steps, **steps_override}

    for stage in stages(
        name=name,
        salt_m=salt_m,
        temperature=temperature,
        backend="CPU" if test_mode else backend,
        **steps,
    ):
        path = directory / f"input_{stage.name}"
        path.write_text(stage.render())
        files[f"input_{stage.name}"] = path

    run = directory / "run.sh"
    run.write_text(RUN_SCRIPT)
    run.chmod(0o755)
    files["run"] = run

    nucleotides = len(ad.topology_bases(files["topology"]))
    from dobladillo.provenance import simulation_record

    metadata = {
        "part": part,
        "design_name": name,
        # The simulation's parent in the provenance chain: which design this
        # is a run of, and the hashes of the topology and starting
        # configuration written from it. `analysis.runs.check_run` checks the
        # topology against this, and `compare --run` the design.
        "provenance": simulation_record(design, part=part, files=files),
        "nucleotides": nucleotides,
        "trapped_pairs": pairs,
        "model": {
            "interaction_type": "DNA2",
            "salt_concentration_m": salt_m,
            "salt_note": (
                "oxDNA2 has no explicit Mg2+. This is a monovalent proxy, and a "
                "prediction made at this value is not comparable to one made at "
                "another, nor directly to a measurement in a magnesium buffer."
            ),
            "temperature": temperature,
        },
        "backend": {
            "name": "CPU" if test_mode else backend,
            **(
                {
                    "fork": METAL_FORK,
                    "commit": METAL_COMMIT,
                    "settings": METAL_SETTINGS,
                    "thermostat": METAL_THERMOSTAT,
                    "thermostat_note": "bussi is not implemented on Metal; john replaces it "
                    "in the MD stages. It changes the dynamics, not the equilibrium.",
                    "validation": METAL_VALIDATION,
                }
                if backend == "Metal" and not test_mode
                else {}
            ),
        },
        "units": {
            "length_unit_nm": OXDNA_LENGTH_UNIT_NM,
            "note": "convert with dobladillo.units, never inline",
        },
        "protocol": {
            "stages": ["01_mc", "02_md_trapped", "03_md_released", "04_production"],
            "source": "oxDNA relaxation guide",
            "deviation_from_design_doc": (
                "DESIGN.md section 3 calls stage 1 energy minimisation. oxDNA has no "
                "such sim_type; its documented first stage is Monte Carlo with capped "
                "backbone forces, which is what is written here."
            ),
        },
        "test_mode": test_mode,
        "steps": dict(steps),
        "status": "not run",
        "owed_by_human": (
            "This bundle has been generated and checked for structure, not executed. "
            "Run it and place the results in data/sim/<design>/ before anything "
            "downstream treats them as real."
            if not test_mode
            else "Test mode: short stages to prove the bundle runs end to end. The "
            "trajectory it produces is not a result and must not be analysed."
        ),
    }
    meta = directory / "metadata.json"
    meta.write_text(json.dumps(metadata, indent=2))
    files["metadata"] = meta

    return JobBundle(
        directory=directory,
        files=files,
        nucleotides=nucleotides,
        trapped_pairs=pairs,
        metadata=metadata,
    )

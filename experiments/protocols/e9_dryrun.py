"""E9 dry run: the assembly-state analysis, on SYNTHETIC scans only.

    uv run python experiments/protocols/e9_dryrun.py --dimer-fraction 0.6 \\
        --out /path/to/e9-dryrun

E1 and E2 ran end to end on synthetic scans before any sample existed, and E4
has `e4_dryrun.py`. This does the same for E9: it builds a whole experiment
folder in a temporary directory -- controls, three replicate mixes and a time
series -- renders each sample's scans with a dimer fraction YOU choose, fills
in the instrument record with the values a session would produce, and runs
`dobladillo experiment assembly` over it. Then it reports what was recovered
next to what was put in.

It takes no data file, and it cannot be pointed at one. Its output says
`"synthetic": true`, and the folder it writes is temporary unless `--out` is
given, in which case the files are marked as synthetic too.

What it exercises, all existing code:

1. `parts.dimer.rectangle_dimer()` -- A and B, and their footprints;
2. `experiments.assembly.new_experiment` -- the folder, the prediction and
   the extras order;
3. `imaging.synthetic.synthetic_assembly_scan` -- monomers and dimers in known
   numbers, with scanner bow, drift and a tip streak;
4. `imaging.readers.write_gsf` -- written into `during/raw/` under the
   protocol's names, `A-01.gsf`, `R1-01.gsf`, ...;
5. `experiments.assembly.analyse` -- the counts, the controls, the intervals
   and the chi-square homogeneity test;
6. E9's proposed gate, applied to the result.

The controls are rendered as monomers only, so the dimer fraction they report
is the analysis's own false-positive rate on this fixture -- which is not the
bench's, because the fixture has no blunt-end stacking in it. What it does
have is the other half of that rate: monomers that land end to end. Pass
`--touching` to raise it.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from dobladillo.experiments.assembly import CONTROLS, MIN_PER_SAMPLE, analyse, new_experiment
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic import synthetic_assembly_scan
from dobladillo.parts.dimer import rectangle_dimer

#: The samples this renders, and how each one behaves. The series is a time
#: course, as the protocol's step 9 asks for: assembly rising towards its
#: plateau, which is what makes "a reproducible distribution" testable.
SERIES: dict[str, float] = {"T15m": 0.25, "T1h": 0.55, "T4h": 0.9, "T24h": 1.0}

#: Particles per sample. Six scans, because a sample that is all dimers has
#: half as many particles as one that is all monomers, and every sample must
#: clear E9's floor of 100 counted particles.
SCANS_PER_SAMPLE = 6
PARTICLES_PER_SCAN = 40

#: What a session would have recorded. Plausible values for a working
#: instrument, and the point of the dry run is that the analysis reads them
#: from the record rather than being handed them.
INSTRUMENT: dict[str, Any] = {
    "instrument": "SYNTHETIC -- this folder holds no real data",
    "mode": "tapping in air",
    "tip": {
        "part_number": "SYNTHETIC",
        "nominal_radius_nm": 10.0,
        "measured_radius_before_nm": 10.0,
        "measured_radius_after_nm": 10.0,
        "note": "synthetic: the fixture renders a 10.0 nm tip, so this is what a "
        "blind estimation of it would return",
    },
    "buffer": {"tris_mm": 5.0, "edta_mm": 1.0, "mgcl2_mm": 12.0, "ph": 8.0},
    "temperature_c": 22.0,
    "scan": {"size_nm": 2000.0, "pixels": 512, "rate_hz": 1.0},
    "reference": {
        "flat_height_nm": 2.0,
        "from": "SYNTHETIC: the fixture's own sheet height, standing in for E1's "
        "measured reference height",
    },
    "synthetic": True,
}


def _compose(fraction: float, *, touching: int) -> dict[str, int]:
    """How many of each particle a sample gets, for a dimer fraction.

    `fraction` is of the rectangles that are in a dimer: with n rectangles per
    scan, d = n * fraction / 2 dimers and n - 2d monomers, so the analysis's
    `rectangles_in_dimers` is what should come back.
    """
    dimers = int(round(PARTICLES_PER_SCAN * fraction / 2))
    monomers = PARTICLES_PER_SCAN - 2 * dimers
    return {
        "monomers": max(monomers - 2 * touching, 0),
        "dimers": dimers,
        "touching_end": touching,
    }


def run(
    *,
    dimer_fraction: float,
    seed: int,
    touching: int,
    root: Path,
) -> dict[str, Any]:
    dimer = rectangle_dimer()
    directory, ordered = new_experiment(root, slug="SYNTHETIC-e9-dry-run", dimer=dimer)
    (directory / "during" / "instrument.json").write_text(json.dumps(INSTRUMENT, indent=2) + "\n")
    (directory / "during" / "log.md").write_text(
        "# Session log\n\nSYNTHETIC. Written by e9_dryrun.py; no session took place.\n"
    )

    monomer_length, width = dimer.monomer_nm
    truth: dict[str, dict[str, Any]] = {}
    plan = {c: 0.0 for c in CONTROLS}
    plan.update({f"R{i}": dimer_fraction for i in (1, 2, 3)})
    plan.update(SERIES)
    for sample, fraction in plan.items():
        composition = _compose(fraction, touching=touching)
        for index in range(1, SCANS_PER_SAMPLE + 1):
            scan = synthetic_assembly_scan(
                length_nm=monomer_length,
                width_nm=width,
                gap_nm=dimer.gap_nm,
                aggregates=1,
                tip_radius_nm=INSTRUMENT["tip"]["measured_radius_before_nm"],
                bow_nm=4.0,
                drift_shear=0.05,
                streak_lines=12,
                seed=seed + 1000 * index + sum(ord(c) for c in sample),
                **composition,
            )
            write_gsf(
                scan.image,
                directory / "during" / "raw" / f"{sample}-{index:02d}.gsf",
                title=f"SYNTHETIC {sample} scan {index}",
            )
            placed = truth.setdefault(
                sample, {"fraction_in": fraction, "monomer": 0, "dimer": 0, "touching_end": 0}
            )
            for particle in scan.truth:
                if particle.kind in ("monomer", "dimer", "touching_end"):
                    placed[particle.kind] += 1

    result = analyse(directory)
    rows = []
    for sample, placed in truth.items():
        counted = result["samples"][sample]
        pairs = placed["dimer"] + placed["touching_end"]
        rectangles = placed["monomer"] + 2 * pairs
        bonded = 2 * placed["dimer"] / rectangles if rectangles else 0.0
        # What a footprint CAN recover: a bonded dimer and two monomers that
        # landed end to end are the same shape, and `imaging.assembly` says so
        # rather than pretending otherwise. So the fixture's own answer to
        # "what should come back" counts both, and the controls are what
        # separates them at the bench.
        by_footprint = 2 * pairs / rectangles if rectangles else 0.0
        recovered = counted["rectangles_in_dimers"]
        rows.append(
            {
                "sample": sample,
                "role": counted["role"],
                "placed": {k: v for k, v in placed.items() if k != "fraction_in"},
                "rectangles_bonded_placed": round(bonded, 4),
                "rectangles_in_dimers_placed": round(by_footprint, 4),
                "rectangles_in_dimers_found": recovered["fraction"],
                "ci95": recovered["ci95"],
                "recovered": recovered["ci95"][0] <= by_footprint <= recovered["ci95"][1],
                "counted": counted["counted"],
                "counts": counted["counts"],
                "excluded_side_by_side": counted["excluded_side_by_side"],
            }
        )

    controls = result["controls"]["dimer_fraction"]
    gate = {
        "controls_dimer_fraction_at_most_0.10": controls["fraction"] <= 0.10,
        "every_mixture_above_controls": all(
            result["samples"][r["sample"]]["dimer_minus_controls"]["above_background"]
            for r in rows
            if r["role"] != "control"
        ),
        "replicates_homogeneous": result["reproducibility"].get("p_value", 1.0) > 0.05,
        "at_least_100_particles_per_sample": not result["too_few_particles"],
        "every_fraction_recovered_in_its_interval": all(r["recovered"] for r in rows),
    }
    return {
        "synthetic": True,
        "dry_run": "E9 rectangle dimer, AFM assembly states",
        "dimer_fraction_asked_for": dimer_fraction,
        "touching_monomer_pairs_per_scan": touching,
        "seed": seed,
        "design_sha256": ordered["design_sha256"],
        "predicted_nm": result["predicted_nm"],
        "controls": result["controls"],
        "reproducibility": result["reproducibility"],
        "samples": rows,
        "too_few_particles": result["too_few_particles"],
        "gate": gate,
        "gate_passed": all(gate.values()),
        "note": "The controls' dimer fraction here is coincidence and end-to-end "
        "touching only: the fixture renders no blunt-end stacking, so it is a floor "
        "on the bench's false-positive rate, not an estimate of it.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--dimer-fraction",
        type=float,
        default=0.6,
        help="fraction of rectangles in a dimer, in the replicate mixes (0 to 1)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--touching",
        type=int,
        default=1,
        help="pairs of unbonded monomers per scan that land end to end: the "
        "false-positive rate the footprint cannot remove",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the folder and the result here instead of a temporary directory",
    )
    args = parser.parse_args(argv)
    if not 0.0 <= args.dimer_fraction <= 1.0:
        parser.error("--dimer-fraction is between 0 and 1")

    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        result = run(
            dimer_fraction=args.dimer_fraction,
            seed=args.seed,
            touching=args.touching,
            root=args.out,
        )
        (args.out / "e9-dryrun.json").write_text(json.dumps(result, indent=2) + "\n")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                dimer_fraction=args.dimer_fraction,
                seed=args.seed,
                touching=args.touching,
                root=Path(tmp),
            )

    print(json.dumps(result, indent=2))
    for row in result["samples"]:
        print(
            f"{row['sample']:>6} ({row['role']}): placed "
            f"{row['rectangles_bonded_placed']:.0%} bonded, "
            f"{row['rectangles_in_dimers_placed']:.0%} dimer-shaped, found "
            f"{row['rectangles_in_dimers_found']:.0%} "
            f"[{row['ci95'][0]:.0%}, {row['ci95'][1]:.0%}] "
            f"{'ok' if row['recovered'] else 'MISSED'}",
            file=sys.stderr,
        )
    for name, passed in result["gate"].items():
        print(f"gate {name}: {'pass' if passed else 'FAIL'}", file=sys.stderr)
    print(
        f"floor for a sample is {MIN_PER_SAMPLE} counted particles",
        file=sys.stderr,
    )
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

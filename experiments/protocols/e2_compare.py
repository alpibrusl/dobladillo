"""E2 readout: compare two blinded arms of the twist pair.

    uv run python experiments/protocols/e2_compare.py \\
        --x during/raw/X-01.spm during/raw/X-02.spm --tip-x 11.2 \\
        --y during/raw/Y-01.spm during/raw/Y-02.spm --tip-y 11.8 \\
        --reference-height 1.3 --out post/arms.json

Written for a blinded run. The person imaging and analysing knows the samples
only as X and Y, so this script never asks which arm is the corrected one. It
reports the difference X - Y and states the verdict both ways; the reading that
applies is chosen after unblinding, by whoever holds the key.

Scans are the instrument's own files (Bruker, JPK, Asylum, Gwyddion, WSXM
.stp) or .gsf exports; see `dobladillo.imaging.readers`. Name one extension,
never `X-*` alone: if a .gsf copy sits beside a native file, that would count
the same image twice.

`--reference-height` is the median height of flat rectangles measured in E1
under the same imaging conditions. It sets what "flat" means: a rolled sheet
is classified by standing taller than a flat one, and dry imaging compresses
everything, so the 2.0 nm of the model is the wrong yardstick on a dried
sample.

To be replaced by a `dobladillo experiment compare-arms` command; until then
this is the supported way to run the E2 comparison.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.imaging.arms import MATERIAL_DIFFERENCE, ArmComparison
from dobladillo.imaging.classify import Population, population
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.readers import read

#: Designed size of each arm, nm.
LENGTH_NM = 191.2
WIDTH_NM = 36.0

#: Below this many counted particles per arm the interval is too wide to
#: separate a real difference from none. From docs/TWIST_PAIR_EXPERIMENT.md.
MIN_PER_ARM = 100


def measure_arm(scans: list[Path], tip_nm: float, reference_height_nm: float) -> dict:
    particles = []
    for scan in scans:
        flattened, background = flatten(read(scan))
        particles.extend(find_particles(flattened, background))
    inside = [p for p in particles if not p.touches_edge]
    if not inside:
        raise SystemExit(f"no particles clear of the frame edge in {[str(s) for s in scans]}")
    observed = statistics.median(p.height_nm for p in inside)
    widening = 2 * half_height_broadening_nm(tip_radius_nm=tip_nm, feature_height_nm=observed)
    found = population(
        particles,
        length_nm=LENGTH_NM + widening,
        width_nm=WIDTH_NM + widening,
        height_nm=reference_height_nm,
    )
    return {"population": found, "widening_nm": widening, "median_height_nm": observed}


def verdict_if(x_is_corrected: bool, comparison: ArmComparison) -> str:
    """The verdict under one unblinding."""
    if x_is_corrected:
        return comparison.verdict
    flipped = ArmComparison(corrected=comparison.uncorrected, uncorrected=comparison.corrected)
    return flipped.verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--x", nargs="+", type=Path, required=True, help="scans of sample X")
    parser.add_argument("--y", nargs="+", type=Path, required=True, help="scans of sample Y")
    parser.add_argument("--tip-x", type=float, required=True, help="measured tip radius for X, nm")
    parser.add_argument("--tip-y", type=float, required=True, help="measured tip radius for Y, nm")
    parser.add_argument(
        "--reference-height",
        type=float,
        required=True,
        help="median flat-sheet height from E1 in the same imaging conditions, nm",
    )
    parser.add_argument("--out", type=Path, help="write the result as JSON here")
    args = parser.parse_args(argv)

    x = measure_arm(args.x, args.tip_x, args.reference_height)
    y = measure_arm(args.y, args.tip_y, args.reference_height)
    px: Population = x["population"]
    py: Population = y["population"]

    from dobladillo.imaging.arms import flat_fraction

    comparison = ArmComparison(corrected=flat_fraction(px), uncorrected=flat_fraction(py))
    low, high = comparison.ci95
    too_few = [name for name, p in (("X", px), ("Y", py)) if p.total < MIN_PER_ARM]

    result = {
        "X": {
            "counts": px.counts,
            "total": px.total,
            "flat_fraction": comparison.corrected.value,
            "widening_nm": round(x["widening_nm"], 2),
            "median_height_nm": round(x["median_height_nm"], 2),
        },
        "Y": {
            "counts": py.counts,
            "total": py.total,
            "flat_fraction": comparison.uncorrected.value,
            "widening_nm": round(y["widening_nm"], 2),
            "median_height_nm": round(y["median_height_nm"], 2),
        },
        "difference_x_minus_y": round(comparison.difference, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "distinguishable": comparison.distinguishable,
        "material_threshold": MATERIAL_DIFFERENCE,
        "verdict_if_x_is_corrected": verdict_if(True, comparison),
        "verdict_if_y_is_corrected": verdict_if(False, comparison),
        "too_few_particles": too_few,
        "reference_height_nm": args.reference_height,
    }

    print(
        f"X: {comparison.corrected.count}/{px.total} flat ({comparison.corrected.value:.0%})"
        f"   counts {px.counts}"
    )
    print(
        f"Y: {comparison.uncorrected.count}/{py.total} flat ({comparison.uncorrected.value:.0%})"
        f"   counts {py.counts}"
    )
    print(f"difference X - Y: {comparison.difference:+.0%}   95% [{low:+.0%}, {high:+.0%}]")
    print(f"if X is the corrected arm:  {result['verdict_if_x_is_corrected']}")
    print(f"if Y is the corrected arm:  {result['verdict_if_y_is_corrected']}")
    if too_few:
        print(
            f"WARNING: fewer than {MIN_PER_ARM} counted particles in {', '.join(too_few)}; "
            "the gate requires at least that many per arm",
            file=sys.stderr,
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 1 if too_few else 0


if __name__ == "__main__":
    raise SystemExit(main())

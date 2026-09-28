"""E4 dry run: the bracketing ladder, read by bulk FRET, on SYNTHETIC data only.

    uv run python experiments/protocols/e4_dryrun.py --offset-kt 20 --seed 0 \\
        --out /path/to/e4-dryrun.json

E1 and E2 ran end to end on synthetic AFM scans before any sample existed.
This does the same for E4, so the analysis chain is exercised and graded
before €307 of latch staples is ordered. It takes no data file on purpose: it
generates a plate from a conformational offset YOU choose, runs the
calibration and estimation on it, applies E4's gate, and reports the offset
it recovered next to the one it was given. It cannot be pointed at a real
plate, and its output says `"synthetic": true` everywhere it matters.

The chain, all of it existing code:

1. `hamiltonian.bracket.ladder()` -- the eight rungs and their predicted
   fields (from sequence, at 25 C and 12 mM Mg);
2. the true p(latched) of each rung, p = 1 / (1 + exp(-2 (f - c/2))), for the
   offset c given here (`Ladder.rung_for` uses the same convention);
3. `fret_synthetic.synthetic_plate` -- one well per rung, plus blank,
   donor-only, acceptor-only and the two locked references;
4. `fret_estimate.estimate_plate` -- background, leakage, direct excitation,
   gamma and beta, then p per rung;
5. E4's gate (`experiments/roadmaps/epic-2-bistable-hinge.md`): at least one
   rung with 0.05 < p < 0.95. Each informative rung gives the field
   h = ln(p / (1 - p)) / 2 and so an offset c = 2 (f - h).

`--gamma` supplies a calibration instead of fitting one -- the negative
control. A wrong one is caught by the stoichiometry gap and the run refuses
to state a verdict (exit 2).

What the real E4 analysis still owes is listed in
`dobladillo/hamiltonian/fret_estimate.py`'s docstring.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from dobladillo.hamiltonian.bracket import INFORMATIVE_PROBABILITY, ladder, probability
from dobladillo.hamiltonian.fret_estimate import estimate_plate
from dobladillo.hamiltonian.fret_synthetic import Calibration, synthetic_plate


def run(offset_kt: float, seed: int, gamma: float | None = None) -> dict[str, Any]:
    rungs = ladder().rungs
    names = {f"bracket-{r.length_bp}bp-{r.sequence}": r for r in rungs}
    truth = {name: probability(r.field_kt - offset_kt / 2.0) for name, r in names.items()}
    calibration = Calibration()
    plate = synthetic_plate(seed=seed, samples=truth, calibration=calibration)
    estimates = estimate_plate(plate, gamma=gamma, beta=None if gamma is None else calibration.beta)

    low, high = INFORMATIVE_PROBABILITY
    rows = []
    for name, rung in names.items():
        est = estimates[name]
        p = est.p_latched
        row: dict[str, Any] = {
            "rung": name,
            "predicted_field_kt": round(rung.field_kt, 2),
            "p_true": round(truth[name], 4),
            "p_measured": round(p, 4),
            "p_stderr": round(est.p_stderr, 4),
            "informative": low < p < high,
        }
        if row["informative"]:
            h = 0.5 * math.log(p / (1.0 - p))
            # dh/dp = 1 / (2 p (1 - p)); c = 2 (f - h), so dc = 2 dh
            row["offset_kt"] = round(2.0 * (rung.field_kt - h), 2)
            row["offset_stderr_kt"] = round(est.p_stderr / (p * (1.0 - p)), 2)
        rows.append(row)

    informative = [r for r in rows if r["informative"]]
    any_estimate = next(iter(estimates.values()))
    consistent = any_estimate.gamma_consistent
    if not consistent:
        verdict = "REFUSED: gamma inconsistent with the locked references; no verdict"
    elif informative:
        verdict = "gate passed: at least one rung reads informatively"
    else:
        verdict = (
            "gate failed: no rung reads informatively; the offset is outside the "
            "ladder's range and the joint length, not the latch, has to change"
        )
    return {
        "synthetic": True,
        "dry_run": "E4 bracketing ladder, bulk FRET",
        "conditions": plate.conditions,
        "offset_true_kt": offset_kt,
        "offset_recovered_kt": [r["offset_kt"] for r in informative],
        "calibration_true": {
            "gamma": calibration.gamma,
            "beta": calibration.beta,
            "leakage": calibration.leakage,
            "direct_excitation": calibration.direct_excitation,
        },
        "calibration_used": any_estimate.corrections.as_dict(),
        "stoichiometry_gap": round(any_estimate.stoichiometry_gap, 4),
        "gamma_consistent": consistent,
        "rungs": rows,
        "gate_passed": bool(consistent and informative),
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument(
        "--offset-kt",
        type=float,
        required=True,
        help="the conformational cost of closing to simulate, kT (the unknown E4 locates)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--gamma", type=float, help="use this gamma instead of fitting one (negative control)"
    )
    parser.add_argument("--out", type=Path, help="write the result as JSON here")
    args = parser.parse_args(argv)

    result = run(args.offset_kt, args.seed, args.gamma)
    print("E4 DRY RUN -- synthetic data, not a measurement")
    for r in result["rungs"]:
        extra = f"  offset {r['offset_kt']:.1f} kT" if r["informative"] else ""
        print(
            f"  {r['rung']:28s} f {r['predicted_field_kt']:5.2f} kT  "
            f"p true {r['p_true']:.3f}  measured {r['p_measured']:.3f}{extra}"
        )
    print(f"offset given {result['offset_true_kt']} kT, recovered {result['offset_recovered_kt']}")
    print(result["verdict"])
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    if not result["gamma_consistent"]:
        print("calibration inconsistent: stoichiometry gap too large", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""E8 dry run: the patterned rectangle, end to end, on SYNTHETIC scans only.

    uv run python experiments/protocols/e8_dryrun.py --out /tmp/e8-dryrun
    uv run python experiments/protocols/e8_dryrun.py --out /tmp/e8-dryrun --realistic

E1-E4 were walked through the toolchain before any sample existed; this does
the same for E8, with the commands the protocol tells a student to type. It
makes a throwaway experiment folder under `--out` (never under
`experiments/`), writes synthetic detail scans into its `during/raw/`, fills
`during/instrument.json` with values that SAY they are synthetic, and runs:

1. `dobladillo lab order pattern` -- the 28 marked staples, and the E1 wells
   to leave out of the pool;
2. `dobladillo experiment new <slug> --part pattern` -- the folder;
3. `dobladillo afm read` on one scan -- pixel size;
4. `dobladillo experiment check` -- the record;
5. `dobladillo experiment pattern` -- `post/pattern.json`;
6. the gate PROPOSED in `E8-patterned-rectangle.md`, applied to the result.

What the synthetic session holds, all chosen here and printed with the result:
the patterned sample lands marks-up half the time (Rothemund 2006 saw 42%
face-up for his 'DNA' pattern, S = 55; this picks 50%), and a face-down sheet
shows no marks. `--missing` of the marks are knocked out on every sheet. The
control sample is E1's plain rectangle. None of it is a prediction of what a
real session will show; it is a known answer for the chain to recover.

It cannot be pointed at real data, and every file it writes says
`synthetic` where it matters.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic_pattern import patterned_scan
from dobladillo.parts.pattern import patterned_rectangle

SLUG = "2026-10-01-e8-dryrun"


def _cli(*args: str) -> dict[str, Any]:
    run = CliRunner().invoke(app, [*args, "--json"])
    payload: dict[str, Any] = json.loads(run.stdout) if run.stdout.strip() else {}
    payload["_exit"] = run.exit_code
    return payload


def proposed_gate(result: dict[str, Any]) -> dict[str, Any]:
    """The gate the protocol PROPOSES. The experimentalist writes the real one."""
    sample = result["pattern"]["pattern"]
    control = (result.get("control") or {}).get("pattern")
    marked = sample["found_among_marked"]
    either = sample["found"]
    checks = {
        "G1 at least 100 well-formed particles read": sample["read"] >= 100,
        "G2 marks spell the design: 95% lower bound of pattern-or-mirror among "
        "marked particles above 50%": marked["ci95"][0] > 0.5,
        "G3 visible at all: pattern-or-mirror in at least 20% of well-formed particles": (
            either["fraction"] >= 0.2
        ),
        "G4 control: at least 50 unmarked rectangles read, at most 5% as the pattern": (
            control is not None and control["read"] >= 50 and control["found"]["fraction"] <= 0.05
        ),
    }
    return {"checks": checks, "passes": all(checks.values())}


def run(
    out: Path, *, mark_nm: float, missing: float, tip_nm: float, seed: int, realistic: bool
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    part = patterned_rectangle()
    steps: dict[str, Any] = {}

    order = _cli("lab", "order", "pattern", "--out", str(out / "order"))
    steps["lab order"] = {
        "exit": order["_exit"],
        "oligos": order.get("wells"),
        "cost": order.get("cost", {}).get("estimated_total"),
        "omit_from_e1": len(order.get("reuse", {}).get("omit_from_base", [])),
    }

    new = _cli("experiment", "new", SLUG, "--part", "pattern", "--root", str(out))
    steps["experiment new"] = {"exit": new["_exit"], "directory": new.get("directory")}
    directory = out / SLUG

    record = json.loads((directory / "during" / "instrument.json").read_text())
    record["instrument"] = "SYNTHETIC dry run -- not an instrument"
    record["tip"]["measured_radius_before_nm"] = tip_nm
    record["tip"]["measured_radius_after_nm"] = tip_nm
    record["buffer"]["mgcl2_mm"] = 12.5
    record["temperature_c"] = 25.0
    record["reference"] = {"flat_height_nm": 2.0, "from": "SYNTHETIC: the renderer's sheet"}
    (directory / "during" / "instrument.json").write_text(json.dumps(record, indent=2) + "\n")

    # Half the patterned sheets marks-up, as either half turn; half face-down.
    patterned = [
        ("identity", "marks"),
        ("rotated_180", "marks"),
        ("identity", "none"),
        ("rotated_180", "none"),
    ] * 3
    raw = directory / "during" / "raw"
    # As `afm synthetic --realistic`: bow, drift shear, one tip streak.
    artefacts: dict[str, Any] = (
        {"bow_nm": 4.0, "drift_shear": 0.05, "streak_lines": 12} if realistic else {}
    )
    placed = {"pattern": 0, "control": 0}
    for i in range(12):
        scan = patterned_scan(
            part.grid,
            sheet_nm=part.dimensions_nm,
            placements=patterned,
            size_px=512,
            scan_nm=1000.0,
            mark_height_nm=mark_nm,
            missing_fraction=missing,
            tip_radius_nm=tip_nm,
            seed=seed + i,
            **artefacts,
        )
        write_gsf(scan.image, raw / f"pattern-{i + 1:02d}.gsf", title="SYNTHETIC")
        placed["pattern"] += len(scan.truth)
    for i in range(6):
        scan = patterned_scan(
            part.grid,
            sheet_nm=part.dimensions_nm,
            placements=[("identity", "none")] * 12,
            size_px=512,
            scan_nm=1000.0,
            tip_radius_nm=tip_nm,
            seed=seed + 100 + i,
            **artefacts,
        )
        write_gsf(scan.image, raw / f"control-{i + 1:02d}.gsf", title="SYNTHETIC")
        placed["control"] += len(scan.truth)
    steps["placed"] = placed

    read = _cli("afm", "read", str(raw / "pattern-01.gsf"))
    steps["afm read"] = {"exit": read["_exit"], "pixel_nm": read.get("pixel_nm")}
    check = _cli("experiment", "check", str(directory))
    steps["experiment check"] = {"exit": check["_exit"], "problems": check.get("problems")}
    pattern = _cli("experiment", "pattern", str(directory))
    steps["experiment pattern"] = {"exit": pattern["_exit"], "error": pattern.get("error")}

    result = json.loads((directory / "post" / "pattern.json").read_text())
    summary = {
        "synthetic": True,
        "settings": {
            "mark_height_nm": mark_nm,
            "missing_fraction": missing,
            "tip_radius_nm": tip_nm,
            "marks_up_fraction": 0.5,
            "realistic_artefacts": realistic,
            "seed": seed,
        },
        "steps": steps,
        "pattern": result["pattern"]["pattern"],
        "control": result["control"]["pattern"] if result["control"] else None,
        "population": result["pattern"]["population"],
        "proposed_gate": proposed_gate(result),
    }
    (out / "e8-dryrun.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="A scratch directory.")
    parser.add_argument("--mark-nm", type=float, default=1.0, help="Mark height, nm.")
    parser.add_argument("--missing", type=float, default=0.2, help="Fraction of marks missing.")
    parser.add_argument("--tip-nm", type=float, default=10.0, help="Tip radius, nm.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--realistic", action="store_true", help="Add scanner bow, drift shear and a streak."
    )
    args = parser.parse_args()
    if "experiments" in args.out.resolve().parts:
        print("refusing to write a synthetic folder under experiments/", file=sys.stderr)
        return 2
    summary = run(
        args.out,
        mark_nm=args.mark_nm,
        missing=args.missing,
        tip_nm=args.tip_nm,
        seed=args.seed,
        realistic=args.realistic,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["proposed_gate"]["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

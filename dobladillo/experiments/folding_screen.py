"""E11: how fast, and at what constant temperature, does a design fold?

The readout is gel band intensities, measured by a person in Fiji (open
source) and written to `during/gel_quant.csv`, one row per lane:

    time_min,temperature_c,folded_band,reference_band

- `folded_band`: the integrated intensity of the folded band in that lane;
- `reference_band`: the same band in the SAME gel's reference lane, E1's
  standard ramp fold. Normalising within a gel cancels staining, loading and
  imaging, which differ between gels far more than folding does.

This module computes the yield relative to the standard fold for every
(time, temperature). It then names, per time, the temperature with the best
yield, and the earliest time at which any temperature reaches the
standard fold's yield within a tolerance. It sets the measured window beside
the predicted one (`sequence.folding`), which is what that prediction is
judged against.

It judges nothing: the gate is the experimentalist's, in `pre/plan.md`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from dobladillo.experiments.arms import RecordIncomplete

#: A lane reaching this fraction of the standard fold's band counts as
#: "folds as well as the ramp". Not a gate: a reporting threshold, and the
#: experimentalist's gate may use another.
AS_GOOD_AS_THE_RAMP: Final = 0.8

COLUMNS: Final = ("time_min", "temperature_c", "folded_band", "reference_band")


@dataclass(frozen=True)
class Lane:
    time_min: float
    temperature_c: float
    relative_yield: float


def read_quantification(directory: Path) -> list[Lane]:
    """Read `during/gel_quant.csv`, refusing rather than guessing."""
    path = directory / "during" / "gel_quant.csv"
    if not path.is_file():
        raise RecordIncomplete(
            "no during/gel_quant.csv: quantify each gel lane in Fiji and write one row per "
            f"lane with columns {', '.join(COLUMNS)} (see the E11 protocol, step 9)",
            kind="no_quantification",
        )
    lanes: list[Lane] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise RecordIncomplete(
                f"during/gel_quant.csv lacks column(s) {', '.join(missing)}",
                kind="bad_quantification",
            )
        for number, row in enumerate(reader, start=2):
            try:
                values = {c: float(row[c]) for c in COLUMNS}
            except (TypeError, ValueError):
                raise RecordIncomplete(
                    f"during/gel_quant.csv line {number}: every column must be a number",
                    kind="bad_quantification",
                ) from None
            if values["reference_band"] <= 0:
                raise RecordIncomplete(
                    f"during/gel_quant.csv line {number}: the reference band must be positive; "
                    "a gel whose standard fold shows no band cannot normalise anything",
                    kind="bad_quantification",
                )
            lanes.append(
                Lane(
                    time_min=values["time_min"],
                    temperature_c=values["temperature_c"],
                    relative_yield=values["folded_band"] / values["reference_band"],
                )
            )
    if not lanes:
        raise RecordIncomplete("during/gel_quant.csv has no lanes", kind="bad_quantification")
    return lanes


def summarise(lanes: list[Lane], predicted: dict[str, Any] | None = None) -> dict[str, Any]:
    """Best temperature per time, the fastest good fold, and the measured window."""
    times = sorted({lane.time_min for lane in lanes})
    per_time: list[dict[str, Any]] = []
    for t in times:
        here = sorted((x for x in lanes if x.time_min == t), key=lambda x: x.temperature_c)
        best = max(here, key=lambda x: x.relative_yield)
        good = [x.temperature_c for x in here if x.relative_yield >= AS_GOOD_AS_THE_RAMP]
        per_time.append(
            {
                "time_min": t,
                "lanes": [
                    {"temperature_c": x.temperature_c, "relative_yield": round(x.relative_yield, 3)}
                    for x in here
                ],
                "best_temperature_c": best.temperature_c,
                "best_relative_yield": round(best.relative_yield, 3),
                "as_good_as_ramp_c": [min(good), max(good)] if good else None,
            }
        )
    fastest = next((p for p in per_time if p["as_good_as_ramp_c"]), None)
    out: dict[str, Any] = {
        "threshold": AS_GOOD_AS_THE_RAMP,
        "by_time": per_time,
        "fastest_good_fold": (
            {
                "time_min": fastest["time_min"],
                "temperatures_c": fastest["as_good_as_ramp_c"],
                "best_temperature_c": fastest["best_temperature_c"],
            }
            if fastest
            else None
        ),
    }
    if predicted:
        window = predicted.get("staple_tm_c", {})
        out["predicted"] = {
            "staple_tm_c": window,
            "isothermal_screen_c": predicted.get("isothermal_screen_c"),
        }
        if fastest and window:
            best_c = float(fastest["best_temperature_c"])
            out["measured_minus_predicted_median_c"] = round(best_c - float(window["median"]), 1)
    return out

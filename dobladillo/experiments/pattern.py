"""E8's readout: does the pattern appear where it was put, and which way round?

The folder holds two samples imaged in one session: the patterned rectangle
(`during/raw/pattern-*`) and E1's plain rectangle as the negative control
(`during/raw/control-*`). Both are counted and classified exactly as E1 and E2
are -- against the designed footprint plus the measured tip -- and every
well-formed particle is then read by `imaging.pattern`.

**What it reads, and refuses without.**

- `pre/prediction.json`: the footprint, and `design.pattern.grid`, the
  pattern as `experiment new` recorded it. The grid comes from the record and
  not from rebuilding the part, for the same reason every comparison in
  `post/` does: the prediction is what was predicted, even if the part's
  defaults move later.
- `during/instrument.json`: the tip radius measured before the session (and
  after, if it was), and `reference.flat_height_nm`, E1's median height of a
  flat rectangle imaged the same way. The first sets the footprint the image
  should show; the second what "flat" means. Neither is replaced by a nominal
  value. Same fields, same refusals, as `experiments.arms`.
- the scans. Only images fine enough to resolve a cell are read for the
  pattern (`imaging.pattern.MIN_PIXELS_PER_CELL`); a 2 x 2 um overview at 512
  pixels is not, and is listed as skipped rather than read badly.

**What it does not do** is evaluate the gate. The gate is in `pre/plan.md`,
written by the experimentalist; `post/pattern.json` has the numbers it needs.
The control is optional in the record -- a session without it still produces
a result -- but its absence is written into the result, because without it
nothing shows that an unmarked sheet does not read as marked.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.experiments.arms import RecordIncomplete
from dobladillo.experiments.instrument import read_instrument
from dobladillo.imaging.pattern import (
    MIN_PIXELS_PER_CELL,
    SPOT_SIGMA,
    PatternGrid,
    Reading,
    background_noise_nm,
    read_particle,
    readable,
    summarise,
)
from dobladillo.readings import Measured, combine, require_measured

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladillo.imaging.classify import Population

#: Scan name prefixes in during/raw, by sample.
SAMPLES: Final = ("pattern", "control")

#: Half-height threshold at the plateau, not at the marks: see
#: `imaging.particles.find_particles`.
PEAK_PERCENTILE: Final = 50.0


@dataclass(frozen=True)
class PatternRecord:
    tip_radius: Measured[float]
    reference_height_nm: float
    reference_from: str
    length_nm: float
    width_nm: float
    grid: PatternGrid
    predicted_from: Path


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_record(directory: Path) -> PatternRecord:
    """Everything the readout needs from the folder, refusing on the first gap."""
    prediction_path = directory / "pre" / "prediction.json"
    if not prediction_path.is_file():
        raise RecordIncomplete(
            "no pre/prediction.json: there is nothing this experiment could be "
            "compared against. It cannot be written now -- see experiments/README.md.",
            kind="no_prediction",
        )
    prediction = json.loads(prediction_path.read_text())
    predicted = prediction.get("predicted_nm", {})
    length, width = _number(predicted.get("length")), _number(predicted.get("width"))
    if length is None or width is None:
        raise RecordIncomplete(
            "pre/prediction.json has no predicted_nm length and width", kind="no_prediction"
        )
    grid_data = ((prediction.get("design") or {}).get("pattern") or {}).get("grid")
    if not grid_data:
        raise RecordIncomplete(
            "pre/prediction.json records no pattern (design.pattern.grid): this folder "
            "was not made for a patterned part. `dobladillo experiment new <slug> --part "
            "pattern` makes one that is.",
            kind="no_pattern",
        )
    grid = PatternGrid.from_dict(grid_data)

    try:
        record = read_instrument(directory)
    except ValueError as e:
        raise RecordIncomplete(f"during/instrument.json: {e}", kind="invalid_reading") from e
    if record is None:
        raise RecordIncomplete("no during/instrument.json", kind="no_instrument")
    before, after = record.tip["before"], record.tip["after"]
    if before is None:
        raise RecordIncomplete(
            "during/instrument.json has no tip.measured_radius_before_nm. This is not a "
            "field to fill in with the nominal value: a nominal 10 nm tip is routinely "
            "8-20 nm in use, and the footprint a well-formed sheet should show depends on it.",
            kind="no_tip_radius",
        )
    tip = combine(
        [r for r in (before, after) if r is not None],
        "tip_radius",
        source="mean of during/instrument.json: tip.measured_radius_before_nm, _after_nm",
    )

    reference = record.data.get("reference") or {}
    height = _number(reference.get("flat_height_nm"))
    if height is None or height <= 0:
        raise RecordIncomplete(
            "during/instrument.json has no reference.flat_height_nm: E1's median height "
            "of flat rectangles, imaged the same way. It is what 'flat' means here, and "
            "E8 runs after E1 to have it. Not the model's 2.0 nm -- dry imaging "
            "compresses everything.",
            kind="no_reference_height",
        )
    return PatternRecord(
        tip_radius=tip,
        reference_height_nm=height,
        reference_from=str(reference.get("from") or ""),
        length_nm=length,
        width_nm=width,
        grid=grid,
        predicted_from=prediction_path,
    )


def scans_for(directory: Path, sample: str) -> list[Path]:
    """A sample's scans: `pattern-01.spm`, `control-01.jpk`, ... Native files
    first, and never native and `.gsf` together -- the rule `experiment
    report` and `experiments.arms` follow."""
    from dobladillo.imaging.readers import is_native_image

    raw = directory / "during" / "raw"
    files = sorted(p for p in raw.glob(f"{sample}-*") if p.is_file())
    native = [p for p in files if is_native_image(p)]
    return native or [p for p in files if p.suffix.lower() == ".gsf"]


@dataclass(frozen=True)
class ParticleReading:
    scan: str
    label: int
    centre_px: tuple[float, float]
    length_nm: float
    width_nm: float
    reading: Reading

    def as_dict(self) -> dict[str, Any]:
        return {
            "scan": self.scan,
            "label": self.label,
            "centre_px": [round(v, 1) for v in self.centre_px],
            "length_nm": round(self.length_nm, 1),
            "width_nm": round(self.width_nm, 1),
            **self.reading.as_dict(),
        }


@dataclass(frozen=True)
class SampleResult:
    scans: tuple[Path, ...]
    skipped: tuple[tuple[Path, str], ...]
    population: Population | None
    widening_nm: float | None
    readings: tuple[ParticleReading, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scans": [str(s) for s in self.scans],
            "skipped": [{"scan": str(s), "why": why} for s, why in self.skipped],
            "population": None if self.population is None else self.population.as_dict(),
            "widening_nm": None if self.widening_nm is None else round(self.widening_nm, 2),
            "pattern": summarise([p.reading for p in self.readings]).as_dict(),
            "particles": [p.as_dict() for p in self.readings],
        }


def measure_sample(
    scans: Sequence[Path], record: PatternRecord, *, spot_sigma: float = SPOT_SIGMA
) -> SampleResult:
    """Count, classify, and read the pattern on every well-formed particle."""
    from dobladillo.imaging.classify import classify, population
    from dobladillo.imaging.flatten import flatten
    from dobladillo.imaging.particles import find_particles
    from dobladillo.imaging.readers import read

    tip = require_measured(record.tip_radius, "tip_radius", parameter="measure_sample's tip")
    grid = record.grid
    read_scans, skipped, found = [], [], []
    for scan in scans:
        image = read(scan)
        if not readable(image, grid):
            skipped.append(
                (
                    scan,
                    f"{image.pixel_nm:.2f} nm per pixel: a {grid.min_cell_nm:.1f} nm cell needs "
                    f"at least {MIN_PIXELS_PER_CELL:g} pixels across; use it for counting, "
                    "image a detail scan for the pattern",
                )
            )
            continue
        flattened, background = flatten(image)
        noise = background_noise_nm(flattened, background)
        particles = find_particles(flattened, background, peak_percentile=PEAK_PERCENTILE)
        read_scans.append(scan)
        found.append((scan, flattened, noise, particles))

    everything = [p for _, _, _, ps in found for p in ps]
    inside = [p for p in everything if not p.touches_edge]
    if not inside:
        return SampleResult(tuple(read_scans), tuple(skipped), None, None, ())
    observed = statistics.median(p.height_nm for p in inside)
    widening = 2 * half_height_broadening_nm(tip_radius_nm=tip.value, feature_height_nm=observed)
    expected = {
        "length_nm": record.length_nm + widening,
        "width_nm": record.width_nm + widening,
        "height_nm": record.reference_height_nm,
    }
    counted = population(everything, **expected)

    readings = []
    for scan, image, noise, particles in found:
        for particle in particles:
            if particle.touches_edge or classify(particle, **expected) != "well_formed":
                continue
            readings.append(
                ParticleReading(
                    scan=scan.name,
                    label=particle.label,
                    centre_px=particle.centre_px,
                    length_nm=particle.length_nm,
                    width_nm=particle.width_nm,
                    reading=read_particle(
                        image, particle, grid, noise_nm=noise, spot_sigma=spot_sigma
                    ),
                )
            )
    return SampleResult(tuple(read_scans), tuple(skipped), counted, widening, tuple(readings))


def result(
    record: PatternRecord, measured: dict[str, SampleResult | None], *, spot_sigma: float
) -> dict[str, Any]:
    """What `post/pattern.json` holds."""
    grid = record.grid
    out: dict[str, Any] = {
        "designed": {
            "pattern_seen_from_marked_face": grid.render().splitlines(),
            "marked_cells": len(grid.on),
            "min_distance": grid.min_distance,
            "decoding_radius": grid.decoding_radius,
            "footprint_nm": {"length": record.length_nm, "width": record.width_nm},
            "predicted_from": str(record.predicted_from),
        },
        "reading": {
            "spot_sigma": spot_sigma,
            "rule": (
                "a cell is marked when its inner median stands above the sheet by more than "
                "spot_sigma x the background noise and half the tallest cells' excess; a "
                "particle reads 'pattern' or 'mirrored' when some half turn or mirror of the "
                "design is within decoding_radius cells of what it shows"
            ),
            "convention": (
                "images are taken as seen from the tip with row 0 at the top. A face-up "
                "particle then reads 'pattern'. If every particle reads 'mirrored', suspect "
                "the file's row order before the sample"
            ),
        },
        "tip_radius_nm": round(record.tip_radius.value, 3),
        "tip_radius": record.tip_radius.as_dict(),
        "reference_height_nm": record.reference_height_nm,
        "reference_from": record.reference_from,
    }
    for sample in SAMPLES:
        sample_result = measured.get(sample)
        out[sample] = None if sample_result is None else sample_result.as_dict()
    if measured.get("control") is None:
        out["control_note"] = (
            "no during/raw/control-* scans: nothing in this record shows that an unmarked "
            "rectangle does not read as marked"
        )
    return out


def report_markdown(directory: Path, out: dict[str, Any], problems: Sequence[str]) -> str:
    """`post/pattern.md`: the page a person reads, with room for the interpretation.

    Everything above the line is regenerated by every run, like `experiment
    report`'s `post/report.md`; the interpretation below it is the
    experimentalist's.
    """
    lines = [
        f"# {directory.name}: pattern",
        "",
        "*Generated by `dobladillo experiment pattern`. Edit the interpretation below",
        "the line; everything above it is regenerated and will be overwritten.*",
        "",
        "Designed, seen from the marked face:",
        "",
        "```",
        *out["designed"]["pattern_seen_from_marked_face"],
        "```",
        "",
        f"- tip radius {out['tip_radius_nm']:.1f} nm; reference flat height "
        f"{out['reference_height_nm']:g} nm ({out['reference_from'] or 'source not given'})",
        f"- a particle shows the pattern when at most {out['designed']['decoding_radius']} of "
        f"the cells disagree with it, turned or mirrored",
        "",
        "| sample | well-formed read | pattern | mirrored | not found | blank "
        "| pattern either way, of all | of those showing marks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sample in SAMPLES:
        if out[sample] is None:
            lines.append(f"| {sample} | no scans | | | | | | |")
            continue
        s = out[sample]["pattern"]
        v, f, m = s["verdicts"], s["found"], s["found_among_marked"]
        lines.append(
            f"| {sample} | {s['read']} | {v['pattern']} | {v['mirrored']} | {v['not_found']} "
            f"| {v['blank']} | {f['fraction']:.0%} [{f['ci95'][0]:.0%}, {f['ci95'][1]:.0%}] "
            f"| {m['fraction']:.0%} [{m['ci95'][0]:.0%}, {m['ci95'][1]:.0%}] |"
        )
    lines.append("")
    for sample in SAMPLES:
        for skipped in (out[sample] or {}).get("skipped", []):
            lines.append(f"- skipped {skipped['scan']}: {skipped['why']}")
    if "control_note" in out:
        lines += [f"- **{out['control_note']}**"]
    if problems:
        lines += ["", "## Problems with the record", ""] + [f"- {p}" for p in problems]
    lines += [
        "",
        "## Against the gate",
        "",
        "The gate is in `pre/plan.md`. Nothing here evaluates it.",
        "",
        "---",
        "",
        "## Interpretation",
        "",
        "",
    ]
    return "\n".join(lines)

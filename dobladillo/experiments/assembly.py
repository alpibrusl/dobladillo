"""E9's readout: assembly states per sample, read from what the folder records.

A and B are imaged alone -- the controls -- and mixed, as replicates and as a
series (time or magnesium). For each sample this counts monomers, dimers,
larger particles and malformed ones with a Wilson interval each
(`imaging.assembly`), and then says three things:

1. **the false-positive rate**: the dimer fraction of A alone and B alone,
   pooled. Two monomers that land end to end are a dimer by footprint, and
   blunt-end stacking the tails failed to stop is one by chemistry; the
   controls measure both at once;
2. **each mixture against it**: the difference in dimer fraction with a
   Newcombe interval, the same interval E2 uses for two proportions;
3. **reproducibility**: whether the replicate mixes share one distribution
   of states (chi-square homogeneity).

**Samples are named by their files**, as E2's X and Y are:
`during/raw/<sample>-<NN>.<ext>`. `A-*` and `B-*` are the controls,
`R1-*`, `R2-*`, ... the replicates, and any other name (`T15m-*`, `T24h-*`,
`Mg10-*`) a sample reported on its own. The names are the protocol's; the
files are never renamed to fit them.

**It refuses rather than substitutes**, like `experiment report`: no measured
tip radius, no reference height from E1, no controls -- each stops it, with a
`kind` an agent can branch on. The reference height matters more here than in
E1: a stacked pair is recognised by standing taller than one flat layer, and
dry imaging makes the model's 2.0 nm the wrong yardstick.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.experiments.arms import RecordIncomplete
from dobladillo.experiments.instrument import read_instrument
from dobladillo.imaging.arms import ArmComparison
from dobladillo.imaging.assembly import (
    AssemblyPopulation,
    Footprints,
    assembly_population,
    reproducibility,
)
from dobladillo.imaging.classify import Fraction
from dobladillo.readings import Measured, combine, require_measured

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladillo.parts.dimer import Dimer

#: The controls: each component imaged alone.
CONTROLS: Final = ("A", "B")

#: Replicate mixes at the standard condition.
REPLICATE: Final = re.compile(r"^R\d+$")

#: A sample's files: `<sample>-<NN>.<ext>`.
SAMPLE_FILE: Final = re.compile(r"^(?P<sample>.+)-(?P<index>\d+)$")

#: Below this many counted particles a sample's fractions are too loose to
#: compare -- E1's floor, for the same reason: +-9 points at 100 particles.
MIN_PER_SAMPLE: Final = 100


@dataclass(frozen=True)
class AssemblyRecord:
    """What the folder says, typed."""

    tip_radius: Measured[float]
    reference_height_nm: float
    reference_from: str
    monomer_length_nm: float
    width_nm: float
    dimer_length_nm: float
    predicted_from: Path


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_record(directory: Path) -> AssemblyRecord:
    """Everything the analysis needs, refusing on the first gap."""
    prediction_path = directory / "pre" / "prediction.json"
    if not prediction_path.is_file():
        raise RecordIncomplete(
            "no pre/prediction.json: there is nothing this experiment could be "
            "compared against. It cannot be written now -- see experiments/README.md.",
            kind="no_prediction",
        )
    prediction = json.loads(prediction_path.read_text())
    predicted = prediction.get("predicted_nm", {})
    length = _number(predicted.get("length"))
    width = _number(predicted.get("width"))
    dimer = _number(predicted.get("dimer_length"))
    if length is None or width is None or dimer is None:
        raise RecordIncomplete(
            "pre/prediction.json has no predicted_nm length, width and dimer_length: "
            "it was not made for an assembly experiment (`experiment new --part dimer`)",
            kind="not_an_assembly",
        )

    try:
        record = read_instrument(directory)
    except ValueError as e:
        raise RecordIncomplete(f"during/instrument.json: {e}", kind="invalid_reading") from e
    if record is None:
        raise RecordIncomplete("no during/instrument.json", kind="no_instrument")
    readings = [r for r in (record.tip["before"], record.tip["after"]) if r is not None]
    if record.tip["before"] is None:
        raise RecordIncomplete(
            "during/instrument.json has no tip.measured_radius_before_nm. This is not a "
            "field to fill in with the nominal value: a nominal 10 nm tip is routinely "
            "8-20 nm in use, and the footprint windows that tell a monomer from a dimer "
            "are set by it. Measure it (common-techniques s8).",
            kind="no_tip_radius",
        )
    tip = combine(
        readings,
        "tip_radius",
        source="mean of during/instrument.json: tip.measured_radius_before_nm, _after_nm",
    )

    reference = record.data.get("reference") or {}
    height = _number(reference.get("flat_height_nm"))
    if height is None or height <= 0:
        raise RecordIncomplete(
            "during/instrument.json has no reference.flat_height_nm: E1's median height "
            "of flat rectangles, imaged the same way. A particle counts as more than one "
            "layer by standing taller than that; the model's 2.0 nm is the wrong "
            "yardstick for dry imaging, and nothing here will assume it.",
            kind="no_reference_height",
        )
    return AssemblyRecord(
        tip_radius=tip,
        reference_height_nm=height,
        reference_from=str(reference.get("from") or ""),
        monomer_length_nm=length,
        width_nm=width,
        dimer_length_nm=dimer,
        predicted_from=prediction_path,
    )


def samples_in(directory: Path) -> dict[str, list[Path]]:
    """Every sample's scans, by file name. Native files first, as everywhere.

    A sample with native files uses only those; its `.gsf` exports are copies
    and reading both would count every particle twice. Files that do not match
    `<sample>-<NN>` (a gel photograph, a README) are not scans of a sample.
    """
    from dobladillo.imaging.readers import is_native_image

    raw = directory / "during" / "raw"
    found: dict[str, dict[str, list[Path]]] = {}
    for path in sorted(raw.iterdir()) if raw.is_dir() else []:
        if not path.is_file():
            continue
        native = is_native_image(path)
        if not native and path.suffix.lower() != ".gsf":
            continue
        match = SAMPLE_FILE.match(path.stem)
        if match is None:
            continue
        bucket = found.setdefault(match["sample"], {"native": [], "gsf": []})
        bucket["native" if native else "gsf"].append(path)
    return {name: b["native"] or b["gsf"] for name, b in sorted(found.items())}


@dataclass(frozen=True)
class SampleMeasurement:
    population: AssemblyPopulation
    footprints: Footprints
    median_height_nm: float
    scans: tuple[Path, ...]


def measure_sample(
    scans: Sequence[Path], *, tip_radius: Measured[float], record: AssemblyRecord
) -> SampleMeasurement:
    """Count one sample's particles into assembly states.

    The tip widening is set by this sample's own median particle height, as in
    `experiment report`; the single-layer yardstick is E1's reference height.
    `tip_radius` must be `Measured`, checked at run time.
    """
    tip = require_measured(tip_radius, "tip_radius", parameter="measure_sample's tip_radius")
    from dobladillo.imaging.flatten import flatten
    from dobladillo.imaging.particles import find_particles
    from dobladillo.imaging.readers import read

    particles = []
    for scan in scans:
        flattened, background = flatten(read(scan))
        particles.extend(find_particles(flattened, background))
    inside = [p for p in particles if not p.touches_edge]
    if not inside:
        raise RecordIncomplete(
            f"no particles clear of the frame edge in {[str(s) for s in scans]}",
            kind="no_particles",
        )
    observed = statistics.median(p.height_nm for p in inside)
    footprints = Footprints(
        monomer_length_nm=record.monomer_length_nm,
        width_nm=record.width_nm,
        dimer_length_nm=record.dimer_length_nm,
        widening_nm=2
        * half_height_broadening_nm(tip_radius_nm=tip.value, feature_height_nm=observed),
        reference_height_nm=record.reference_height_nm,
    )
    return SampleMeasurement(
        population=assembly_population(particles, footprints),
        footprints=footprints,
        median_height_nm=observed,
        scans=tuple(scans),
    )


def _difference(mixture: Fraction, control: Fraction) -> dict[str, Any]:
    """Mixture minus control dimer fraction, with Newcombe's interval.

    `ArmComparison` is E2's container for two proportions; its interval is the
    Newcombe score interval for a difference, which is what this needs. Its
    slot names are E2's and mean nothing here.
    """
    compared = ArmComparison(corrected=mixture, uncorrected=control)
    low, high = compared.ci95
    return {
        "difference": round(compared.difference, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "above_background": low > 0,
    }


def analyse(directory: Path) -> dict[str, Any]:
    """Everything `post/assembly.json` holds. Raises RecordIncomplete on a gap."""
    record = read_record(directory)
    samples = samples_in(directory)
    if not samples:
        raise RecordIncomplete(
            "no scans in during/raw named <sample>-<NN>: expected A-01.spm, B-01.spm, "
            "R1-01.spm, ... (see experiments/protocols/E9-rectangle-dimer.md)",
            kind="no_scans",
        )
    missing = [c for c in CONTROLS if c not in samples]
    if missing:
        raise RecordIncomplete(
            f"no scans of the control(s) {', '.join(missing)} (during/raw/{missing[0]}-*). "
            "A and B imaged alone are the false-positive rate: two monomers touching end "
            "to end are a dimer by footprint, and without the controls a dimer fraction "
            "cannot be told from background.",
            kind="no_controls",
        )

    measured = {
        name: measure_sample(scans, tip_radius=record.tip_radius, record=record)
        for name, scans in samples.items()
    }
    background = Fraction(
        sum(measured[c].population.counts["dimer"] for c in CONTROLS),
        sum(measured[c].population.total for c in CONTROLS),
    )

    per_sample: dict[str, Any] = {}
    for name, m in measured.items():
        role = "control" if name in CONTROLS else "replicate" if REPLICATE.match(name) else "series"
        entry: dict[str, Any] = {
            "role": role,
            **m.population.as_dict(),
            "median_height_nm": round(m.median_height_nm, 2),
            "footprints": m.footprints.as_dict(),
            "scans": [str(s) for s in m.scans],
        }
        if role != "control":
            entry["dimer_minus_controls"] = _difference(m.population.fraction("dimer"), background)
        per_sample[name] = entry

    replicates = {n: measured[n].population for n in measured if REPLICATE.match(n)}
    repro: dict[str, Any] | None = None
    if len(replicates) >= 2:
        repro = reproducibility(replicates).as_dict()

    too_few = [n for n, m in measured.items() if m.population.total < MIN_PER_SAMPLE]
    tip = record.tip_radius
    return {
        "experiment": "E9 rectangle dimer",
        "samples": per_sample,
        "controls": {
            "samples": list(CONTROLS),
            "dimer_fraction": background.as_dict(),
            "meaning": "false-positive rate: monomers touching end to end, plus any "
            "stacking the 4-T tails did not stop",
        },
        "reproducibility": repro
        or {"note": "fewer than two replicate samples (R1-*, R2-*, ...); not assessed"},
        "min_per_sample": MIN_PER_SAMPLE,
        "too_few_particles": too_few,
        "tip_radius_nm": round(tip.value, 3),
        "tip_blunting_fraction": round((tip.uncertainty or 0.0) / tip.value, 3),
        "tip_radius": tip.as_dict(),
        "reference_height_nm": record.reference_height_nm,
        "reference_from": record.reference_from,
        "predicted_nm": {
            "monomer_length": record.monomer_length_nm,
            "width": record.width_nm,
            "dimer_length": record.dimer_length_nm,
        },
        "predicted_from": str(record.predicted_from),
    }


# ------------------------------------------------------------ the folder


def prediction_for(dimer: Dimer) -> dict[str, Any]:
    """`pre/prediction.json` for an E9 folder: footprints, not a yield.

    Nothing here predicts how many dimers form. What is recorded is what a
    monomer and a dimer should look like, and the design they are of.
    """
    from dobladillo import __version__, provenance

    dims = dimer.as_dict(with_report=False)["approx_dimensions_nm"]
    return {
        "part": "dimer",
        "generated_by": f"dobladillo {__version__}",
        "provenance": provenance.design_record(dimer.design_hash(), part="dimer"),
        "predicted_nm": {
            "length": dims["monomer_length"],
            "width": dims["monomer_width"],
            "height": 2.0,
            "dimer_length": dims["dimer_length"],
            "gap": dims["gap"],
        },
        "assembly": {
            "states": ["monomer", "dimer", "larger", "malformed"],
            "excluded": ["touching the frame edge", "side by side (long edges touching)"],
            "predicted": "A alone and B alone: monomers, dimer fraction at background. "
            "A + B: dimers above background. No yield is predicted.",
            "samples": {
                "controls": list(CONTROLS),
                "replicates": "R1, R2, R3, ...",
                "series": "any other name, e.g. T15m, T1h, T4h, T24h or Mg8, Mg12, Mg16",
            },
        },
        "design": dimer.as_dict(),
        "gate": {
            "criterion": "FILL THIS IN BEFORE TAKING DATA",
            "note": "What result would make this experiment a failure? Write it here "
            "first. A gate decided afterwards is a description of the data.",
        },
    }


PLAN: Final = """\
# {slug}

**Part.** `dimer` -- two E1 rectangles, A and B, joined end to end by eleven
12-nt sticky ends. Protocol: `experiments/protocols/E9-rectangle-dimer.md`.

## What this is for

Whether two separately folded origami assemble as designed, and whether the
distribution of assembly states -- monomer, dimer, larger, malformed -- comes
out the same from one mix to the next.

## The gate

**Write this before taking data.** What result makes this a failure? The
protocol proposes one; the decision is the experimentalist's.

> criterion:

## What is predicted

| quantity | predicted |
|---|---|
| monomer | {length} x {width} nm |
| dimer | {dimer_length} x {width} nm |
| height | {height} nm |

Every footprint is measured wider by the tip; `experiment assembly` adds that
back using the tip radius in `during/instrument.json`, which is why the field
is not optional. No yield is predicted.

## Checklist before starting

- [ ] Gate written above
- [ ] `pre/` committed to git, so the prediction provably predates the data
- [ ] Extras ordered from `pre/order/`; E1's plates at hand
- [ ] E1's magnesium and reference height known
- [ ] Tip radius measured and written into `during/instrument.json`
"""

PROTOCOL: Final = """\
# dimer: protocol

Follow `experiments/protocols/E9-rectangle-dimer.md`; it is the protocol for
this folder. Record every deviation in `during/log.md` rather than editing
this file. The pooling -- which E1 wells to take and which to skip -- is in
`pre/order/dimer_pools.json`.
"""


def new_experiment(root: Path, *, slug: str, dimer: Dimer) -> tuple[Path, dict[str, Any]]:
    """Scaffold an E9 folder: prediction, plan, protocol pointer, and the order."""
    from dobladillo.experiments.layout import scaffold
    from dobladillo.lab.dimer import order

    prediction = prediction_for(dimer)
    predicted = prediction["predicted_nm"]
    directory = scaffold(
        root,
        slug=slug,
        prediction=prediction,
        plan=PLAN.format(slug=slug, **predicted),
        protocol=PROTOCOL,
    )
    ordered = order(dimer, directory=directory / "pre" / "order")
    return directory, ordered

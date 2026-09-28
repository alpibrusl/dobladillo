"""E2's readout: two blinded arms, compared from what the folder records.

The twist pair is imaged blind. Whoever deposits, images and analyses knows
the two samples only as X and Y; a second person holds the key. So nothing
here asks which arm is the corrected one, and nothing could use the answer if
it were given. The comparison is computed once, as X against Y, and the verdict
is stated under **both** unblindings. The one that applies is chosen after the
interpretation is committed, by whoever opens the envelope.

This used to be `experiments/protocols/e2_compare.py`, with the tip radii and
the reference height passed as arguments. It moved into the package for the
same reason `experiment report` reads the tip radius from the folder rather
than from a flag: a number typed at a prompt is the easiest place for a
nominal value to stand in for a measured one, and nothing downstream can tell.
Everything this needs is read from the record, and a missing value stops it.

**What it reads.**

- `pre/prediction.json` -- the designed length and width of an arm. Recorded
  when the folder was made, like every other comparison in `post/`.
- `during/instrument.json` -- three tip radii, `tip.measured_radius_before_nm`,
  `..._between_nm` and `..._after_nm`, and `imaging_order`, the order the two
  arms were imaged in. E2 measures the tip between the samples because a tip
  that blunts mid-session means X and Y were imaged with different tips. Each
  arm's radius is the mean of the two readings on either side of it, which is
  the protocol's rule; the code applies it so that nobody writes a derived
  number into a file meant for readings.
- `during/instrument.json`'s `reference.flat_height_nm` -- E1's median height
  of flat rectangles, in the same imaging conditions. It sets what "flat"
  means: dry imaging compresses everything, so the model's 2.0 nm is the wrong
  yardstick, and a rolled sheet is recognised only by standing taller than a
  flat one measured the same way.
- `during/raw/X-*` and `during/raw/Y-*` -- the scans, named by arm: native files, or
  `.gsf` exports when the format is not read directly.

**What it gates.** At least `MIN_PER_ARM` counted particles per arm, from the
gate in `pre/plan.md` and `docs/TWIST_PAIR_EXPERIMENT.md`. Fewer is reported,
written down and returned as a failure, not quietly turned into a verdict from
an interval too wide to mean anything.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.experiments.instrument import read_instrument
from dobladillo.imaging.arms import MATERIAL_DIFFERENCE, ArmComparison, flat_fraction
from dobladillo.readings import Measured, combine, require_measured

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladillo.imaging.classify import Population

Arm = Literal["X", "Y"]

#: The two blinded labels, in the order results are reported. Not the order
#: they were imaged in: that is a coin flip, recorded in `imaging_order`.
ARMS: Final[tuple[Arm, Arm]] = ("X", "Y")

#: Below this many counted particles per arm the interval is too wide to
#: separate a real difference from none. From docs/TWIST_PAIR_EXPERIMENT.md,
#: and the gate in the E2 folder's pre/plan.md says the same.
MIN_PER_ARM: Final = 100


class RecordIncomplete(Exception):
    """The folder lacks something the comparison needs, and it will not guess.

    `kind` is stable, for an agent to branch on; the message says what is
    missing and why it cannot be filled in from anything else.
    """

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class ArmRecord:
    """What the folder says about the session, per arm."""

    #: Each arm's tip: the mean of the two readings either side of it, with
    #: their spread as its uncertainty.
    tip_radius: dict[Arm, Measured[float]]
    reference_height_nm: float
    reference_from: str
    imaging_order: tuple[Arm, Arm]
    length_nm: float
    width_nm: float
    predicted_from: Path


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_record(directory: Path) -> ArmRecord:
    """Read everything the comparison needs, refusing on the first gap.

    The refusals are the design. A missing between-sample tip reading is not
    replaced by the before and after mean, a missing reference height is not
    replaced by the model's 2.0 nm, and a missing imaging order is not assumed
    to be alphabetical: each substitution produces a plausible number that is
    wrong in a way nothing downstream can detect.
    """
    prediction_path = directory / "pre" / "prediction.json"
    if not prediction_path.is_file():
        raise RecordIncomplete(
            "no pre/prediction.json: there is nothing this experiment could be "
            "compared against. It cannot be written now -- see experiments/README.md.",
            kind="no_prediction",
        )
    predicted = json.loads(prediction_path.read_text()).get("predicted_nm", {})
    length, width = _number(predicted.get("length")), _number(predicted.get("width"))
    if length is None or width is None:
        raise RecordIncomplete(
            "pre/prediction.json has no predicted_nm length and width for an arm",
            kind="no_prediction",
        )

    try:
        record = read_instrument(directory)
    except ValueError as e:
        raise RecordIncomplete(f"during/instrument.json: {e}", kind="invalid_reading") from e
    if record is None:
        raise RecordIncomplete("no during/instrument.json", kind="no_instrument")
    instrument = record.data

    readings = record.tip
    absent = [name for name, value in readings.items() if value is None]
    if absent:
        fields = ", ".join(f"tip.measured_radius_{name}_nm" for name in absent)
        raise RecordIncomplete(
            f"during/instrument.json has no {fields}. E2 needs the tip measured "
            "before, between and after the two samples, because a tip that blunts "
            "mid-session images X and Y with different tips. This is not a field to "
            "fill in with the nominal value or with a neighbouring reading: the "
            "correction goes as sqrt(R), and a guess turns one outcome into another.",
            kind="no_tip_radius",
        )

    order = instrument.get("imaging_order")
    if not isinstance(order, list) or sorted(order) != list(ARMS):
        raise RecordIncomplete(
            'during/instrument.json needs "imaging_order": ["X", "Y"] or ["Y", "X"], '
            "the order the two arms were imaged in. It decides which tip readings "
            "bracket which arm, and it was a coin flip, so it cannot be assumed.",
            kind="no_imaging_order",
        )
    first: Arm = order[0]
    second: Arm = order[1]

    reference = instrument.get("reference") or {}
    height = _number(reference.get("flat_height_nm"))
    if height is None or height <= 0:
        raise RecordIncomplete(
            "during/instrument.json has no reference.flat_height_nm: the median "
            "height of flat rectangles from E1, imaged the same way. It is what "
            "'flat' means here. Not the model's 2.0 nm -- dry imaging compresses "
            "everything, and against the wrong yardstick every flat sheet in both "
            "arms reads as twisted, or every twisted one as flat.",
            kind="no_reference_height",
        )

    before, between, after = (readings["before"], readings["between"], readings["after"])
    assert before is not None and between is not None and after is not None
    brackets = {
        first: ([before, between], "before_nm and _between_nm"),
        second: ([between, after], "between_nm and _after_nm"),
    }
    radius = {
        arm: combine(
            pair,
            "tip_radius",
            source=f"mean of during/instrument.json: tip.measured_radius_{fields}",
        )
        for arm, (pair, fields) in brackets.items()
    }

    return ArmRecord(
        tip_radius=radius,
        reference_height_nm=height,
        reference_from=str(reference.get("from") or ""),
        imaging_order=(first, second),
        length_nm=length,
        width_nm=width,
        predicted_from=prediction_path,
    )


def scans_for(directory: Path, arm: Arm) -> list[Path]:
    """An arm's scans, by the protocol's naming: `X-01.spm`, `Y-01.jpk`, ...

    Native files first, and never native and `.gsf` together -- the same rule
    as `experiment report`: an export sits beside its native original, and
    reading both would count every image twice.
    """
    from dobladillo.imaging.readers import is_native_image

    files = sorted(p for p in (directory / "during" / "raw").glob(f"{arm}-*") if p.is_file())
    native = [p for p in files if is_native_image(p)]
    return native or [p for p in files if p.suffix.lower() == ".gsf"]


@dataclass(frozen=True)
class ArmMeasurement:
    """One arm, counted."""

    population: Population
    widening_nm: float
    median_height_nm: float
    scans: tuple[Path, ...]


def measure_arm(
    scans: Sequence[Path],
    *,
    tip_radius: Measured[float],
    reference_height_nm: float,
    length_nm: float,
    width_nm: float,
) -> ArmMeasurement:
    """Count one arm's particles into flat, twisted, malformed and aggregate.

    Classified against what the IMAGE should show -- the arm plus the tip --
    rather than the arm itself, for the reason `afm measure` gives: comparing a
    broadened footprint to the object's own size marks every particle
    malformed. The broadening is set by the measured height of this arm's
    particles, while the height class is set by the reference: the first is a
    fact about the tip, the second about what a flat sheet looks like here.

    `tip_radius` must be `Measured`, checked at run time too: this is a public
    function, and the likeliest wrong call passes the nominal radius.
    """
    tip = require_measured(tip_radius, "tip_radius", parameter="measure_arm's tip_radius")
    from dobladillo.imaging.classify import population
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
    widening = 2 * half_height_broadening_nm(tip_radius_nm=tip.value, feature_height_nm=observed)
    found = population(
        particles,
        length_nm=length_nm + widening,
        width_nm=width_nm + widening,
        height_nm=reference_height_nm,
    )
    return ArmMeasurement(
        population=found, widening_nm=widening, median_height_nm=observed, scans=tuple(scans)
    )


def verdict_if(x_is_corrected: bool, comparison: ArmComparison) -> str:
    """The verdict under one unblinding.

    `comparison` is built with X in the `corrected` slot, which is a
    convenience of the arithmetic and not a claim. Unblinding the other way
    swaps the slots, which negates the difference and mirrors the interval.
    """
    if x_is_corrected:
        return comparison.verdict
    flipped = ArmComparison(corrected=comparison.uncorrected, uncorrected=comparison.corrected)
    return flipped.verdict


def compare_blinded(x: ArmMeasurement, y: ArmMeasurement) -> ArmComparison:
    """X against Y. Positive difference means X lay flat more often."""
    return ArmComparison(
        corrected=flat_fraction(x.population), uncorrected=flat_fraction(y.population)
    )


def result(
    record: ArmRecord, measured: dict[Arm, ArmMeasurement], comparison: ArmComparison
) -> dict[str, Any]:
    """What `post/arms.json` holds. Both verdicts, never one."""
    low, high = comparison.ci95
    fractions = {"X": comparison.corrected, "Y": comparison.uncorrected}
    tip = record.tip_radius
    arms: dict[str, Any] = {}
    for arm in ARMS:
        m = measured[arm]
        arms[arm] = {
            "counts": m.population.counts,
            "total": m.population.total,
            "flat_fraction": fractions[arm].value,
            "widening_nm": round(m.widening_nm, 2),
            "median_height_nm": round(m.median_height_nm, 2),
            "tip_radius_nm": round(tip[arm].value, 3),
            "tip_blunting_fraction": round((tip[arm].uncertainty or 0.0) / tip[arm].value, 3),
            "tip_radius": tip[arm].as_dict(),
            "scans": [str(s) for s in m.scans],
        }
    too_few = [arm for arm in ARMS if measured[arm].population.total < MIN_PER_ARM]
    return {
        **arms,
        "difference_x_minus_y": round(comparison.difference, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "distinguishable": comparison.distinguishable,
        "material_threshold": MATERIAL_DIFFERENCE,
        "verdict_if_x_is_corrected": verdict_if(True, comparison),
        "verdict_if_y_is_corrected": verdict_if(False, comparison),
        "min_per_arm": MIN_PER_ARM,
        "too_few_particles": too_few,
        "reference_height_nm": record.reference_height_nm,
        "reference_from": record.reference_from,
        "imaging_order": list(record.imaging_order),
        "designed_arm_nm": {"length": record.length_nm, "width": record.width_nm},
        "predicted_from": str(record.predicted_from),
    }

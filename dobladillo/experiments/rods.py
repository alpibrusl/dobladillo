"""E10's readout: is the six-helix bundle straight, and is it the right length?

The bundle is this project's first 3D part, and the first one whose failure
mode was a shape rather than a size. Its earlier routings bent it, in oxDNA,
into arcs of 269 and 347 nm radius (docs/BUNDLE_BEND.md). The current routing
is phased like published designs and the beam model predicts it straight.
This is the physical check.

The question is not "are the rods bent?" -- every adsorbed rod is, a little,
because a persistence length of microns is not infinite -- but **whether the
bending is thermal or built in**. `imaging.wlc` separates the two by how the
tangent-angle variance grows along the rod: linearly for thermal bending,
quadratically for an arc. This module turns a folder's scans into that fit,
and into the length check that goes with it.

**What it reads.**

- `pre/prediction.json` -- the designed length and diameter, and the `rods`
  block written by `experiment new` for this part: what a straight flexible
  rod and what the old arcs would look like. A folder made before that block
  existed is reported with the prediction computed now and flagged as not
  pre-registered, never silently.
- `during/instrument.json` -- the tip radius measured before and after
  (`tip.measured_radius_before_nm`, `_after_nm`). Refused if missing, for the
  reason `experiment report` gives: a nominal tip turns one answer into another
  and nothing downstream can tell. Optionally `reference.flat_height_nm`, E1's
  flat-sheet height in the same imaging conditions, which the report quotes
  beside the rod height and does not use to correct it.
- `during/raw/` -- the scans, native first, as `experiment report` does.

**Classes**, in the order they are decided, each a stated boundary rather
than a tuned one:

- `aggregate`: taller than `AGGREGATE_HEIGHT_FACTOR` times the median height of
  the population's own unbranched elongated particles. Not the design
  diameter: dry imaging compresses a bundle by an amount nobody here has
  measured, so the population is its own yardstick;
- `branched`: a side branch longer than two apparent widths -- two rods
  crossing, or something stuck to one (`imaging.rods`);
- `compact`: aspect below `MIN_ROD_ASPECT` -- a blob, a collapsed scaffold, a
  short fragment seen end-on;
- `rod`, `short`, `long`: by tip-corrected contour against the design,
  within `classify.SHAPE_TOLERANCE`. `long` is usually two rods end to end.

Only `rod` enters the straightness analysis. Classifying by contour length
does not bias the curvature: an arc has the same contour as a straight rod.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo.compare import (
    Conditions,
    Observation,
    compare,
    deconvolve_tip,
    designed,
    half_height_broadening_nm,
)
from dobladillo.constants import PERSISTENCE_LENGTH_6HB_NM
from dobladillo.experiments.arms import RecordIncomplete
from dobladillo.experiments.instrument import read_instrument
from dobladillo.imaging import wlc
from dobladillo.imaging.classify import SHAPE_TOLERANCE, Fraction
from dobladillo.readings import Measured, combine, require_measured

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladillo.imaging.rods import Trace

#: The radii of curvature oxDNA gave the two misphased bundle routings, nm:
#: 269 +- 11 for the original 21/21 routing and 347 +- 51 for the 28/14 one
#: (docs/BUNDLE_BEND.md, 200-frame production runs). Simulation results, not
#: measurements, and of earlier designs -- used here only as what "the old
#: defect, back again" would look like.
OLD_ARC_RADII_NM: Final = (269.0, 347.0)

#: Below this many counted rods the curvature bound is too loose to separate
#: "straight" from an arc of a micron. From the synthetic calibration in
#: tests/test_rods.py: at about 90 rods a 1 um intrinsic radius is detected,
#: and the old arcs are resolved to +-20%.
MIN_RODS: Final = 100

#: A particle taller than this multiple of the population's single-rod height
#: is more than one object. Same factor as for sheets (classify.py).
AGGREGATE_HEIGHT_FACTOR: Final = 1.6

#: Contour over apparent width below which a particle is not a rod. A 390 nm
#: bundle images about 20 nm wide at a 10 nm tip, aspect ~20; a quarter-length
#: fragment is ~5.
MIN_ROD_ASPECT: Final = 4.0

#: Tip radii for the planning table in the prediction: the range a nominal
#: 10 nm tip is "routinely" found at in use (experiments/AGENTS.md). Planning
#: only; the analysis uses the measured radius.
PLANNING_TIP_RADII_NM: Final = (8.0, 10.0, 15.0, 20.0)

#: Shapes drawn per population for the predicted distributions.
PREDICTION_SAMPLES: Final = 4000


# ------------------------------------------------------------- prediction


def cylinder_half_height_broadening_nm(*, tip_radius_nm: float, feature_height_nm: float) -> float:
    """Per-side broadening at half height of a round rod, for a spherical tip.

    A cylinder of radius r = h/2 lying on the surface; the tip centre touches
    it at R + r from the axis, so the apex is at z = r - R + sqrt((R+r)^2 - x^2)
    and crosses half height (z = r) at x = sqrt(r^2 + 2 R r). The object's own
    half-height half-width is r. `compare.half_height_broadening_nm` assumes a
    flat-topped plateau, which is right for a sheet and for a rod's END face,
    and over-corrects a rod's WIDTH: 8.0 against 5.8 nm per side for an 8 nm rod
    and a 10 nm tip. Both are reported; neither is chosen for you.
    """
    if tip_radius_nm <= 0 or feature_height_nm <= 0:
        raise ValueError("tip radius and feature height must be positive")
    r = feature_height_nm / 2.0
    return math.sqrt(r * r + 2.0 * tip_radius_nm * r) - r


def predict_rods(
    *,
    contour_nm: float,
    diameter_nm: float,
    lp_range_nm: tuple[float, float] = PERSISTENCE_LENGTH_6HB_NM,
    arc_radii_nm: Sequence[float] = OLD_ARC_RADII_NM,
    samples: int = PREDICTION_SAMPLES,
    seed: int = 0,
) -> dict[str, Any]:
    """What an AFM of these rods should show, if straight and if curved like the old design.

    Deterministic for a seed, so a prediction written into `pre/` can be
    regenerated and checked.
    """
    low, high = lp_range_nm
    lps = (low, math.sqrt(low * high), high)

    apparent = []
    for radius in PLANNING_TIP_RADII_NM:
        plateau = half_height_broadening_nm(tip_radius_nm=radius, feature_height_nm=diameter_nm)
        cylinder = cylinder_half_height_broadening_nm(
            tip_radius_nm=radius, feature_height_nm=diameter_nm
        )
        apparent.append(
            {
                "tip_radius_nm": radius,
                "contour_nm": round(contour_nm + 2 * plateau, 1),
                "width_nm": round(diameter_nm + 2 * cylinder, 1),
            }
        )

    straight = []
    for i, lp in enumerate(lps):
        shapes = wlc.sample_shapes(samples, contour_nm=contour_nm, lp_nm=lp, seed=seed + i)
        straight.append(
            {
                "persistence_length_nm": round(lp, 0),
                "rms_end_to_end_ratio": round(
                    math.sqrt(wlc.mean_square_end_to_end_2d(contour_nm, lp)) / contour_nm, 4
                ),
                "tangent_variance_at_full_length_rad2": round(contour_nm / lp, 4),
                "intrinsic_curvature_sq_per_nm2": 0.0,
                **wlc.population_statistics(shapes),
            }
        )

    arcs = []
    for j, radius in enumerate(arc_radii_nm):
        for i, lp in enumerate((low, high)):
            shapes = wlc.sample_shapes(
                samples,
                contour_nm=contour_nm,
                lp_nm=lp,
                curvature_per_nm=1.0 / radius,
                seed=seed + 100 + 10 * j + i,
            )
            arcs.append(
                {
                    "arc": wlc.Arc(contour_nm, radius).as_dict(),
                    "persistence_length_nm": round(lp, 0),
                    "tangent_variance_at_full_length_rad2": round(
                        float(wlc.tangent_msd(contour_nm, lp, 1.0 / radius)), 4
                    ),
                    "intrinsic_curvature_sq_per_nm2": 1.0 / radius**2,
                    **wlc.population_statistics(shapes),
                }
            )

    return {
        "model": "2D wormlike chain, optionally with a built-in arc (dobladillo.imaging.wlc)",
        "generated_with_seed": seed,
        "samples_per_population": samples,
        "designed": {"contour_nm": round(contour_nm, 1), "diameter_nm": round(diameter_nm, 1)},
        "planning_apparent_size": {
            "kind": "planning, at nominal tip radii -- NOT a prediction of a measurement",
            "note": "contour: plateau model at each flat end; width: round-rod (cylinder) "
            "model, both with the rod standing at its design diameter. Dry imaging "
            "compresses DNA, so the height -- and with it the broadening -- will be lower "
            "by an amount E1's reference height indicates and nothing here predicts.",
            "rows": apparent,
        },
        "straight_flexible": straight,
        "persistence_length_range_nm": [low, high],
        "persistence_length_from": "dobladillo.constants.PERSISTENCE_LENGTH_6HB_NM",
        "systematic_arc": arcs,
        "arc_radii_from": "docs/BUNDLE_BEND.md: oxDNA arcs of the two misphased routings",
        "discriminator": (
            "fit <dtheta^2>(s) = c + s/Lp + kappa0^2 s^2 over the traced rods. A straight, "
            "flexible bundle gives kappa0^2 consistent with zero; the old defect gives "
            "kappa0 ~ 1/269-1/347 nm^-1. End-to-end/contour alone separates them poorly "
            "(compare the distributions above); the quadratic term separates them well."
        ),
        "assumptions": [
            "the rod equilibrates on the surface, or is trapped with small angles -- the "
            "two agree to leading order in L/Lp (imaging.wlc)",
            "an arc lands with its bend in the surface plane; one landing bent out of the "
            "plane is pressed flat and would read as straight",
            "the design contour uses scadnano's rise per base pair; oxDNA and the beam "
            "model use 0.34 nm/bp, which gives a ~2% longer rod",
        ],
    }


# ------------------------------------------------------------- the record


@dataclass(frozen=True)
class RodRecord:
    """What the folder says, typed."""

    tip_radius: Measured[float]
    contour_nm: float
    diameter_nm: float
    prediction: dict[str, Any]
    prediction_preregistered: bool
    predicted_from: Path
    reference_height_nm: float | None
    magnesium: Measured[float] | None
    temperature: Measured[float] | None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_record(directory: Path) -> RodRecord:
    """Everything the readout needs, refusing on the first gap that cannot be filled honestly."""
    prediction_path = directory / "pre" / "prediction.json"
    if not prediction_path.is_file():
        raise RecordIncomplete(
            "no pre/prediction.json: there is nothing this experiment could be "
            "compared against. It cannot be written now -- see experiments/README.md.",
            kind="no_prediction",
        )
    prediction = json.loads(prediction_path.read_text())
    contour = _number(prediction.get("predicted_nm", {}).get("length"))
    dimensions = (prediction.get("design") or {}).get("approx_dimensions_nm") or {}
    diameter = _number(dimensions.get("diameter"))
    if contour is None or diameter is None:
        raise RecordIncomplete(
            "pre/prediction.json has no designed length and diameter: this readout is "
            "for a rod-shaped part (the six-helix bundle), made with "
            "`experiment new --part bundle`",
            kind="not_a_rod",
        )
    rods = prediction.get("rods")
    preregistered = isinstance(rods, dict)
    if not preregistered:
        rods = predict_rods(contour_nm=contour, diameter_nm=diameter)

    try:
        record = read_instrument(directory)
    except ValueError as e:
        raise RecordIncomplete(f"during/instrument.json: {e}", kind="invalid_reading") from e
    if record is None:
        raise RecordIncomplete("no during/instrument.json", kind="no_instrument")
    readings = [r for r in (record.tip["before"], record.tip["after"]) if r is not None]
    if record.tip["before"] is None:
        raise RecordIncomplete(
            "during/instrument.json has no tip.measured_radius_before_nm. Not a field to "
            "fill in with the nominal value: a nominal 10 nm tip is routinely 8-20 nm in "
            "use, and the correction removed from each rod's contour goes as sqrt(R). "
            "Measure it (common-techniques.md section 8).",
            kind="no_tip_radius",
        )
    tip = combine(
        readings,
        "tip_radius",
        source="mean of during/instrument.json: tip.measured_radius_before_nm, _after_nm",
    )
    reference = (record.data.get("reference") or {}).get("flat_height_nm")
    return RodRecord(
        tip_radius=tip,
        contour_nm=contour,
        diameter_nm=diameter,
        prediction=rods,
        prediction_preregistered=preregistered,
        predicted_from=prediction_path,
        reference_height_nm=_number(reference),
        magnesium=record.magnesium,
        temperature=record.temperature,
    )


# ------------------------------------------------------------ measurement


def classify_traces(
    traces: Sequence[Trace], *, contour_nm: float, tip_radius_nm: float
) -> tuple[list[str], float]:
    """A class for each trace, and the single-rod height the classes were judged against."""
    elongated = [t for t in traces if not t.branched and t.aspect >= MIN_ROD_ASPECT]
    reference = statistics.median(t.height_nm for t in (elongated or traces))
    classes = []
    for t in traces:
        if t.height_nm > AGGREGATE_HEIGHT_FACTOR * reference:
            classes.append("aggregate")
        elif t.branched:
            classes.append("branched")
        elif t.aspect < MIN_ROD_ASPECT:
            classes.append("compact")
        else:
            ends = 2 * half_height_broadening_nm(
                tip_radius_nm=tip_radius_nm, feature_height_nm=max(t.height_nm, 1e-6)
            )
            length = t.contour_nm - ends
            if length < (1 - SHAPE_TOLERANCE) * contour_nm:
                classes.append("short")
            elif length > (1 + SHAPE_TOLERANCE) * contour_nm:
                classes.append("long")
            else:
                classes.append("rod")
    return classes, reference


CLASSES: Final = ("rod", "short", "long", "branched", "compact", "aggregate")


@dataclass(frozen=True)
class RodMeasurement:
    traces: tuple[Trace, ...]
    classes: tuple[str, ...]
    excluded_at_edge: int
    reference_height_nm: float
    scans: tuple[Path, ...]

    @property
    def rods(self) -> list[Trace]:
        return [t for t, c in zip(self.traces, self.classes, strict=True) if c == "rod"]

    @property
    def counts(self) -> dict[str, int]:
        # Fixed keys, so a class that did not occur reports zero rather than
        # vanishing from the totals (the lesson in classify.population).
        return {k: sum(1 for c in self.classes if c == k) for k in CLASSES}


def measure_rods(
    scans: Sequence[Path], *, tip_radius: Measured[float], contour_nm: float
) -> RodMeasurement:
    """Read, flatten and trace every scan; classify what was found."""
    tip = require_measured(tip_radius, "tip_radius", parameter="measure_rods's tip_radius")
    from dobladillo.imaging.flatten import flatten
    from dobladillo.imaging.readers import read
    from dobladillo.imaging.rods import trace_particles

    traces: list[Trace] = []
    for scan in scans:
        flattened, background = flatten(read(scan))
        traces.extend(trace_particles(flattened, background))
    inside = [t for t in traces if not t.touches_edge]
    if not inside:
        raise RecordIncomplete(
            f"no particles clear of the frame edge in {[str(s) for s in scans]}",
            kind="no_particles",
        )
    classes, reference = classify_traces(inside, contour_nm=contour_nm, tip_radius_nm=tip.value)
    return RodMeasurement(
        traces=tuple(inside),
        classes=tuple(classes),
        excluded_at_edge=len(traces) - len(inside),
        reference_height_nm=reference,
        scans=tuple(scans),
    )


def _stats(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        "n": int(array.size),
        "mean": round(float(array.mean()), 2),
        "sd": round(float(array.std(ddof=1)), 2) if array.size > 1 else None,
        "median": round(float(np.median(array)), 2),
        "p2.5": round(float(np.percentile(array, 2.5)), 4),
        "p97.5": round(float(np.percentile(array, 97.5)), 4),
    }


def shape_fit(rods: Sequence[Trace]) -> tuple[wlc.TangentFit, dict[str, Any]]:
    """The tangent fit and the end-to-end cross-check, with the lag window stated."""
    ds = rods[0].ds_nm
    traced = statistics.median(len(t.angles_rad) * t.ds_nm for t in rods)
    width = statistics.median(t.width_nm for t in rods)
    from dobladillo.imaging.rods import SMOOTHING_WIDTHS

    # Beyond three smoothing lengths the tracing noise is a constant, which
    # the fit's intercept absorbs; below 70% of the traced length the longest
    # lags are still averaged over most of the population.
    s_min = max(3 * SMOOTHING_WIDTHS * width, 5 * ds)
    s_max = 0.7 * traced
    fit = wlc.fit_tangent_msd(
        [t.angles_rad for t in rods], ds_nm=ds, s_min_nm=s_min, s_max_nm=s_max
    )
    end_to_end = wlc.lp_from_end_to_end(
        [t.contour_nm for t in rods], [t.end_to_end_nm for t in rods]
    )
    return fit, end_to_end


def result(record: RodRecord, measured: RodMeasurement) -> dict[str, Any]:
    """What `post/rods.json` holds."""
    counts = measured.counts
    total = len(measured.classes)
    rods = measured.rods
    tip = record.tip_radius
    conditions = Conditions(
        temperature_c=record.temperature.value if record.temperature else None,
        magnesium_m=record.magnesium.value / 1000.0
        if record.magnesium and record.magnesium.value
        else None,
        model="AFM, half-height backbone trace",
    )
    out: dict[str, Any] = {
        "scans": [str(s) for s in measured.scans],
        "counted": total,
        "excluded_touching_edge": measured.excluded_at_edge,
        "classes": counts,
        "rod_fraction": Fraction(counts["rod"], total).as_dict(),
        "min_rods": MIN_RODS,
        "too_few_rods": counts["rod"] < MIN_RODS,
        "single_rod_height_nm": round(measured.reference_height_nm, 3),
        "tip_radius_nm": round(tip.value, 3),
        "tip_blunting_fraction": round((tip.uncertainty or 0.0) / tip.value, 3),
        "tip_radius": tip.as_dict(),
        "designed_nm": {"contour": record.contour_nm, "diameter": record.diameter_nm},
        "predicted_from": str(record.predicted_from),
        "prediction_preregistered": record.prediction_preregistered,
        "prediction": record.prediction,
    }
    if not rods:
        out["verdict"] = "no rods: nothing to measure a shape from"
        return out

    height = statistics.median(t.height_nm for t in rods)
    out["rod_height_nm"] = _stats([t.height_nm for t in rods])
    out["height_note"] = (
        "measured, not corrected: dry imaging compresses DNA and there is no geometric "
        "correction for it (compare/corrections.py). Compare with E1's flat-sheet height "
        "in the same conditions, not with the design diameter."
    )
    if record.reference_height_nm:
        out["e1_reference_height_nm"] = record.reference_height_nm
        out["rod_height_over_e1_reference"] = round(height / record.reference_height_nm, 3)

    contours = [t.contour_nm for t in rods]
    raw = Observation(
        quantity="contour_nm",
        value_nm=statistics.fmean(contours),
        definition="afm_half_height",
        origin="measured",
        conditions=conditions,
        uncertainty_nm=statistics.stdev(contours) if len(contours) > 1 else None,
        n=len(contours),
    )
    corrected = deconvolve_tip(raw, feature_height_nm=height, tip_radius_nm=tip)
    contour = compare(
        "contour_nm", [designed("contour_nm", record.contour_nm), corrected.observation]
    )
    out["contour"] = {
        "raw_nm": _stats(contours),
        "tip_correction": corrected.as_dict(),
        "comparison": contour.as_dict(),
        "agrees": contour.agrees,
    }

    widths = [t.width_nm for t in rods]
    mean_width = statistics.fmean(widths)
    plateau = 2 * half_height_broadening_nm(tip_radius_nm=tip.value, feature_height_nm=height)
    cylinder = 2 * cylinder_half_height_broadening_nm(
        tip_radius_nm=tip.value, feature_height_nm=height
    )
    out["width"] = {
        "raw_nm": _stats(widths),
        "corrected_plateau_model_nm": round(mean_width - plateau, 2),
        "corrected_round_rod_model_nm": round(mean_width - cylinder, 2),
        "design_diameter_nm": record.diameter_nm,
        "note": "reported, not judged: the two tip models differ by more than the "
        "diameter's own uncertainty, and a dried bundle is neither a plateau nor a "
        "round rod.",
    }

    ratios = [t.end_to_end_nm / t.contour_nm for t in rods]
    out["end_to_end_ratio"] = _stats(ratios)
    out["sagitta_over_contour"] = _stats([t.sagitta_nm / t.contour_nm for t in rods])
    if len(rods) >= 3:
        fit, end_to_end = shape_fit(rods)
        low, high = record.prediction.get("persistence_length_range_nm", PERSISTENCE_LENGTH_6HB_NM)
        lp_low, lp_high = fit.lp_ci95_nm
        out["tangent_fit"] = fit.as_dict()
        out["end_to_end_fit"] = end_to_end
        out["persistence_length_consistent_with_prediction"] = lp_low <= high and lp_high >= low
        # The gentler of the two old arcs is the one to exclude: ruling out
        # 347 nm rules out 269 nm too.
        excluded = fit.curvature_ci95_per_nm[1] < 1.0 / max(OLD_ARC_RADII_NM)
        out["old_defect_excluded"] = excluded
        out["verdict"] = fit.verdict + (
            "; the old routings' arcs (269-347 nm radius) are excluded"
            if excluded
            else "; the old routings' arcs are NOT excluded"
        )
    else:
        out["verdict"] = "fewer than 3 rods: no shape fit"
    return out

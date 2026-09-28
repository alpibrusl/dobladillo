"""A benchmark of known answers for routing and shape prediction (#14).

The six-helix bundle bent into a 269 nm arc and sat in the repository from Q1
until an oxDNA run found it. It passed six design rules, a cadnano round trip
and pinned staple counts; none of those was scored against a design whose
shape somebody had measured. This module is that score. Any change to routing
(`routing.azimuth`, `routing.rules`) or to the shape predictor
(`mechanics.beam`) is run against it, and `dobladillo benchmark` exits
non-zero when an expectation fails.

**Where the answers come from.** `tests/data/known_answers.json`, one entry
per case, each citing its source. None of them comes from a tool this project
wrote, which is the whole point (VISION.md section 0: a reimplementation
without an independent reference to disagree with is how the worst bugs got
in):

- five **published designs** (`tests/data/reference_designs/`) that folded:
  their crossovers must pass phasing;
- the two **old bundle routings** (`tests/data/our_designs/`), which recorded
  oxDNA runs show bent into arcs of 269 and 347 nm: they must FAIL phasing and
  lint, and `predict` must refuse to vouch for them. These are the negative
  controls. The issue that asked for this benchmark said "the current bundle
  fails it"; that was written while the current bundle was the 28/14 routing.
  Since it was re-tiled onto scadnano's published 6HB unit, the old routings
  are the known-bad cases and the current bundle is expected to PASS;
- the **composite-beam cases**, textbook answers built by the predictor's
  synthetic twin (`mechanics.twin`): a 6HB with one helix wanting to be 1/21
  shorter bends to R = 168.0 nm with twist-stretch coupling off, half the
  strain doubles the radius, and opposite helices shortened together stay
  straight by symmetry;
- one **measured curvature**: the 120 deg bundle of Dietz, Douglas & Shih,
  *Science* 2009, whose design is in caDNAno's BSD-licensed test data and
  whose measured angle (121 +- 8.4 deg) is in the open author manuscript.

**Known failures are data, not exceptions.** Two kinds of case fail today,
and hiding either would be worse than reporting it. Published designs that
folded are rejected by `seed_domain`, `min_domain` and, for the curved one,
`crossover_azimuth` with deletions counted: rules in conflict with published
designs, flagged per AGENTS.md rule 8 rather than relaxed. And the beam model
predicts the Dietz bend as 101 deg against 121 +- 8.4 measured. Each such case
carries `known_failure` with the reason; it is reported as a known failure and
does not fail the run. If one starts passing it is an `unexpected_pass`, which
DOES fail the run -- as `xfail(strict=True)` does -- so the manifest is
updated by a person rather than drifting.

**What is wanted and not obtained** is listed in the manifest's `wanted`
section with the reason, and reported, so the gaps are visible: the other six
Dietz bends and the twisted ribbons (measurements open, designs not found
under an open licence), and the two oxDNA runs still going.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    import scadnano as sc

    from dobladillo.mechanics.twin import BeamTwin

#: Where the manifest lives in a checkout. The designs it names sit beside it.
DEFAULT_MANIFEST: Final = Path(__file__).resolve().parent.parent / "tests/data/known_answers.json"

#: The statuses a case can end in. Only `fail` and `unexpected_pass` fail a run.
STATUSES: Final = ("pass", "fail", "known_failure", "unexpected_pass")


@dataclass(frozen=True)
class CaseResult:
    """One known answer, scored."""

    id: str
    stage: str
    check: str
    design: str
    expect: str
    source: str
    met: bool
    observed: dict[str, Any]
    known_failure: str | None = None

    @property
    def status(self) -> str:
        if self.known_failure is None:
            return "pass" if self.met else "fail"
        return "unexpected_pass" if self.met else "known_failure"

    @property
    def ok(self) -> bool:
        return self.status in ("pass", "known_failure")

    def as_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "stage": self.stage,
            "check": self.check,
            "design": self.design,
            "expect": self.expect,
            "status": self.status,
            "observed": self.observed,
            "source": self.source,
        }
        if self.known_failure is not None:
            out["known_failure"] = self.known_failure
        return out


@dataclass(frozen=True)
class BenchmarkReport:
    cases: tuple[CaseResult, ...]
    wanted: tuple[dict[str, str], ...] = field(default_factory=tuple)
    manifest: str = ""
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cases)

    @property
    def failed(self) -> tuple[CaseResult, ...]:
        return tuple(c for c in self.cases if not c.ok)

    def counts(self) -> dict[str, int]:
        return {s: sum(1 for c in self.cases if c.status == s) for s in STATUSES}

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "counts": self.counts(),
            "cases": [c.as_dict() for c in self.cases],
            "wanted": list(self.wanted),
            "manifest": self.manifest,
            "seconds": round(self.seconds, 1),
        }


# --------------------------------------------------------------- designs


def beam_twin(spec: str) -> BeamTwin:
    """A shape-predictor twin from its manifest name, e.g. `twin:0/21,3/21`.

    Each `helix/period` puts one deletion every `period` bp on that helix of
    the current 6HB (`mechanics.twin`). The answer is composite-beam theory
    or symmetry, never the model.
    """
    from dobladillo.mechanics.twin import shortened_bundle

    body = spec.removeprefix("twin:")
    shortened: dict[int, int] = {}
    for item in filter(None, body.split(",")):
        helix, _, period = item.partition("/")
        shortened[int(helix)] = int(period)
    return shortened_bundle(shortened)


def _part(name: str) -> sc.Design:
    if name == "bundle":
        from dobladillo.parts.bundle import six_helix_bundle

        return six_helix_bundle().design
    if name == "rectangle":
        from dobladillo.parts.rectangle import rothemund_rectangle

        return rothemund_rectangle().design
    raise ValueError(f"unknown part {name!r} in the benchmark manifest")


def load_design(spec: str, root: Path) -> sc.Design:
    """A design named in the manifest: a file beside it, a part, or a beam twin.

    `.json` is cadnano v2 (caDNAno's own test data is in that format), `.sc`
    is scadnano.
    """
    import scadnano as sc

    if spec.startswith("part:"):
        return _part(spec.removeprefix("part:"))
    if spec.startswith("twin:"):
        return beam_twin(spec).design
    path = root / spec
    if path.suffix == ".json":
        return sc.Design.from_cadnano_v2(json_dict=json.loads(path.read_text()))
    return sc.Design.from_scadnano_file(str(path))


def without_helices(design: sc.Design, drop: set[int]) -> sc.Design:
    """A copy of `design` with some helices removed, strands cut where they left.

    For a helix that is in the file but not in the object -- a caDNAno helix
    parking a leftover scaffold loop, joined to the body only by single strand.
    Nothing constrains it, so the beam model's stiffness matrix would be
    singular with it in.
    """
    import scadnano as sc

    strands = []
    for strand in design.strands:
        pieces: list[list[Any]] = [[]]
        for domain in strand.domains:
            if not hasattr(domain, "helix"):
                pieces[-1].append(domain)
            elif domain.helix in drop:
                pieces.append([])
            else:
                pieces[-1].append(
                    sc.Domain(
                        domain.helix,
                        domain.forward,
                        domain.start,
                        domain.end,
                        deletions=list(domain.deletions),
                        insertions=list(domain.insertions),
                    )
                )
        for piece in pieces:
            # a loopout cannot end a strand; keep only runs that start and end on a helix
            while piece and not hasattr(piece[0], "helix"):
                piece.pop(0)
            while piece and not hasattr(piece[-1], "helix"):
                piece.pop()
            if piece:
                strands.append(sc.Strand(domains=piece, is_scaffold=strand.is_scaffold))
    helices = {
        idx: sc.Helix(idx=idx, max_offset=h.max_offset, grid_position=h.grid_position)
        for idx, h in design.helices.items()
        if idx not in drop
    }
    return sc.Design(helices=helices, strands=strands, grid=design.grid)


# ---------------------------------------------------------------- checks


def _expect_bool(case: dict[str, Any], passed: bool) -> bool:
    """Whether a pass/fail observation meets a case's `expect`."""
    expect = case["expect"]
    if expect not in ("pass", "fail"):
        raise ValueError(f"{case['id']}: expect must be 'pass' or 'fail', got {expect!r}")
    return bool(passed == (expect == "pass"))


def check_phasing(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """`routing.azimuth.measure` with deletions counted: the lint rule's view."""
    from dobladillo.routing.azimuth import measure

    report = measure(design)
    observed = {
        "acceptable": report.acceptable,
        "rms_strain_deg": round(report.rms_deg, 1),
        "wrong_face": len(report.wrong_face),
        "crossovers": len(report.crossovers),
    }
    return _expect_bool(case, report.acceptable), observed


def check_placement(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """Phasing by crossover placement only, deletions ignored.

    A curved design strains its crossovers on purpose with deletions and
    insertions; what must hold for it is that every crossover sits where its
    neighbour allows. This is the measure `predict` uses to judge itself.
    """
    from dobladillo.routing.azimuth import measure

    report = measure(design, count_skips=False)
    observed = {
        "acceptable": report.acceptable,
        "rms_strain_deg": round(report.rms_deg, 1),
        "wrong_face": len(report.wrong_face),
        "crossovers": len(report.crossovers),
    }
    return _expect_bool(case, report.acceptable), observed


def check_lint(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """Every rule; passing means no hard violation. Warnings never count."""
    from dobladillo.routing.rules import lint

    report = lint(design)
    hard_by_rule: dict[str, int] = {}
    for v in report.hard:
        hard_by_rule[v.rule] = hard_by_rule.get(v.rule, 0) + 1
    observed = {
        "ok": report.ok,
        "hard": len(report.hard),
        "hard_by_rule": dict(sorted(hard_by_rule.items())),
        "warnings": len(report.warnings),
    }
    return _expect_bool(case, report.ok), observed


def check_prediction_valid(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """Would `dobladillo predict` vouch for its answer on this design?

    The beam model cannot see misphasing, so `predict` marks its answer valid
    only when placement-only phasing passes. A design known to be bent by
    misphasing must be refused, not predicted straight.
    """
    from dobladillo.mechanics.beam import predict
    from dobladillo.routing.azimuth import measure

    valid = measure(design, count_skips=False).acceptable
    shape = predict(design)
    observed = {
        "valid": valid,
        "straight": shape.straight,
        "radius_nm": None if shape.straight else round(shape.radius_nm, 1),
    }
    return _expect_bool(case, valid), observed


def check_composite_beam(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """The beam model against composite-beam theory, via its synthetic twin.

    `design` is the twin's own design; it is rebuilt with its answer here,
    because the answer comes from how it was built, not from the file.
    """
    from dobladillo.mechanics.twin import grade

    (graded,) = grade([beam_twin(case["design"])])
    observed = graded.as_dict()
    observed.pop("source")
    return graded.ok == (case["expect"] == "pass"), observed


def bend_angle_deg(design: sc.Design, parameters: Any = None) -> float:
    """Angle between the two end cross-sections of the solved shape, degrees.

    What a TEM measurement of a bent bundle reports: the angle between its
    arms, whatever the curvature profile between them. From the beam model's
    rotation degrees of freedom, averaged over every helix of the first and
    last full cross-sections. In a linear solve, rotation is the integral of
    curvature, so this holds for large total angles as long as the local
    strain is small.
    """
    from dobladillo.mechanics.beam import BeamParameters, assemble

    system = assemble(design, parameters or BeamParameters())
    u = system.solve()
    helices = sorted(design.helices)
    offsets = sorted({o for (_, o) in system.node})
    full = [o for o in offsets if all((h, o) in system.node for h in helices)]
    if len(full) < 2:
        raise ValueError("no two cross-sections have every helix paired")

    def section(o: int) -> np.ndarray:
        return np.asarray(np.mean([u[system.node[(h, o)], 3:5] for h in helices], axis=0))

    return float(np.degrees(np.linalg.norm(section(full[-1]) - section(full[0]))))


def check_bend_angle(case: dict[str, Any], design: sc.Design) -> tuple[bool, dict[str, Any]]:
    """Predicted angle between the arms, against a measured distribution."""
    from dobladillo.mechanics.beam import BeamParameters

    if case.get("exclude_helices"):
        design = without_helices(design, set(case["exclude_helices"]))
    measured, sd = case["measured_deg"], case["measured_sd_deg"]
    predicted = bend_angle_deg(design)
    # Reported alongside, not scored: which term moves the answer.
    uncoupled = bend_angle_deg(design, BeamParameters(twist_stretch_pn_nm=0.0))
    off_by_sd = (predicted - measured) / sd
    met = abs(off_by_sd) <= case["tolerance_sd"]
    observed = {
        "predicted_deg": round(predicted, 1),
        "measured_deg": measured,
        "measured_sd_deg": sd,
        "measured_n": case.get("measured_n"),
        "off_by_sd": round(off_by_sd, 2),
        "tolerance_sd": case["tolerance_sd"],
        "predicted_without_twist_stretch_coupling_deg": round(uncoupled, 1),
    }
    return met == (case["expect"] == "pass"), observed


CHECKS: Final[dict[str, Callable[[dict[str, Any], sc.Design], tuple[bool, dict[str, Any]]]]] = {
    "phasing": check_phasing,
    "placement": check_placement,
    "lint": check_lint,
    "prediction_valid": check_prediction_valid,
    "composite_beam": check_composite_beam,
    "bend_angle": check_bend_angle,
}

_REQUIRED: Final = ("id", "stage", "check", "design", "expect", "source")


def load_manifest(path: Path) -> dict[str, Any]:
    """Read and validate a manifest. A case with no source is refused.

    The benchmark is only worth anything if every answer in it came from
    somewhere else; an entry that cannot say where is not accepted.
    """
    manifest: dict[str, Any] = json.loads(path.read_text())
    seen: set[str] = set()
    for case in manifest.get("cases", []):
        missing = [k for k in _REQUIRED if not case.get(k)]
        if missing:
            raise ValueError(f"case {case.get('id', '?')!r} lacks {', '.join(missing)}")
        if case["check"] not in CHECKS:
            raise ValueError(f"case {case['id']!r}: unknown check {case['check']!r}")
        if case["id"] in seen:
            raise ValueError(f"case id {case['id']!r} appears twice")
        seen.add(case["id"])
    for entry in manifest.get("wanted", []):
        if not entry.get("why_not"):
            raise ValueError(
                f"wanted entry {entry.get('id', '?')!r} does not say why it is missing"
            )
    return manifest


@contextmanager
def _measure_once() -> Iterator[None]:
    """Compute each design's azimuth report once per run, not three times.

    `phasing`, `lint` (through the `crossover_azimuth` rule) and
    `prediction_valid` each call `routing.azimuth.measure`, and on a large
    design it is the slow part: seconds, from its twist-rate grid search.
    The rule looks the function up on the module at call time, so it is
    wrapped there for the duration of the run and restored after. Keyed on the
    design object, which the run holds for its whole length, so an id cannot
    be reused while the cache is live.
    """
    from dobladillo.routing import azimuth

    original = azimuth.measure
    cache: dict[tuple[int, bool], azimuth.AzimuthReport] = {}

    def cached(design: sc.Design, *, count_skips: bool = True) -> azimuth.AzimuthReport:
        key = (id(design), count_skips)
        if key not in cache:
            cache[key] = original(design, count_skips=count_skips)
        return cache[key]

    azimuth.measure = cached
    try:
        yield
    finally:
        azimuth.measure = original


def run(manifest_path: Path | None = None, *, only: Sequence[str] | None = None) -> BenchmarkReport:
    """Score every case in the manifest, or those whose id starts with one of `only`."""
    with _measure_once():
        return _run(manifest_path, only=only)


def _run(manifest_path: Path | None, *, only: Sequence[str] | None) -> BenchmarkReport:
    started = time.perf_counter()
    path = manifest_path or DEFAULT_MANIFEST
    manifest = load_manifest(path)
    cases = [
        c
        for c in manifest["cases"]
        if not only or any(c["id"].startswith(prefix) for prefix in only)
    ]
    if only and not cases:
        raise ValueError(f"no case id starts with any of {list(only)}")
    designs: dict[str, sc.Design] = {}
    results = []
    for case in cases:
        if case["design"] not in designs:
            designs[case["design"]] = load_design(case["design"], path.parent)
        met, observed = CHECKS[case["check"]](case, designs[case["design"]])
        results.append(
            CaseResult(
                id=case["id"],
                stage=case["stage"],
                check=case["check"],
                design=case["design"],
                expect=case["expect"],
                source=case["source"],
                met=met,
                observed=observed,
                known_failure=case.get("known_failure"),
            )
        )
    return BenchmarkReport(
        cases=tuple(results),
        wanted=tuple(manifest.get("wanted", [])),
        manifest=str(path),
        seconds=time.perf_counter() - started,
    )

"""Design-rule checks, each one composable and each one explaining itself.

The rules are the ones in DESIGN.md section 3, with their thresholds read from
`constants.py` so that relaxing one is a visible edit to a documented number
rather than a quiet change here.

Two severities. A `violation` is a hard constraint: a design that breaks one is
expected to fold badly or not at all. A `warning` is a preference -- staple
length outside the target band, say -- which published designs break routinely
and which should not stop anything.

Every finding carries where it is (strand, helix, offset), because "some staple
is too short" is not actionable and "the staple starting at helix 3 offset 96
is 18 nt" is.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.constants import (
    POLY_G_RUN_FLAG,
    STAPLE_CROSSOVER_CLEARANCE_BP,
    STAPLE_LENGTH_NT,
    STAPLE_LENGTH_TARGET_NT,
    STAPLE_MIN_DOMAIN_NT,
    STAPLE_SEED_DOMAIN_NT,
)

if TYPE_CHECKING:
    import scadnano as sc


class Severity(StrEnum):
    VIOLATION = "violation"
    WARNING = "warning"


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: Severity
    message: str
    helix: int | None = None
    offset: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {**dataclasses.asdict(self), "severity": self.severity.value}


@dataclass(frozen=True)
class Rule:
    name: str
    summary: str
    check: Callable[[sc.Design], Iterator[Violation]]


def _staple_anchor(staple: sc.Strand) -> tuple[int, int]:
    """Where to point at when naming a staple: its first domain's 5' end."""
    first = staple.domains[0]
    return first.helix, (first.start if first.forward else first.end - 1)


def _crossovers(strand: sc.Strand) -> Iterator[tuple[frozenset[int], int]]:
    """Every helix change in a strand, as (helix pair, offset where it happens)."""
    for before, after in zip(strand.domains, strand.domains[1:], strict=False):
        if getattr(before, "helix", None) is None or getattr(after, "helix", None) is None:
            continue  # a loopout or extension, not a domain on a helix
        if before.helix == after.helix:
            continue
        offset = before.end - 1 if before.forward else before.start
        yield frozenset({before.helix, after.helix}), offset


# --------------------------------------------------------------------- checks


def check_crossover_azimuth(design: sc.Design) -> Iterator[Violation]:
    """Each crossover must be made where the backbone faces its partner.

    A crossover joins two helices at one base pair, and the offset of that base
    pair is an angle: the backbone turns about 34 deg per base. Measured by
    `routing.azimuth`, which takes the geometry from scadnano and is calibrated
    on published designs (caDNAno's Nature 2009 test data and scadnano's own
    examples), every one of which scores 18-22 deg rms.

    Three findings:

    - a VIOLATION per crossover more than a quarter-turn off its partner --
      published designs have none;
    - a VIOLATION for the design when its rms phasing strain is above the
      ceiling, even if no single crossover is that far out;
    - a WARNING when the helices carry uncorrected twist. Not a defect in
      itself: E2's control arm carries 310 deg of it on purpose.

    It replaces `crossover_phase`, which compared offsets modulo a fixed period
    and got both directions wrong: it passed the rectangle, whose tiling put
    half its crossovers on the wrong face, and it flagged scadnano's correctly
    phased rectangles, which change partner every 16 bp.
    """
    from dobladillo.routing import azimuth

    if getattr(design.grid, "value", str(design.grid)) not in ("square", "honeycomb"):
        return
    report = azimuth.measure(design)
    for c in report.wrong_face:
        yield Violation(
            rule="crossover_azimuth",
            severity=Severity.VIOLATION,
            message=(
                f"crossover from helix {c.helix} to {c.partner} is {c.strain_deg:.0f} deg "
                "off its partner: the backbone faces away, so the bond strains the duplex"
            ),
            helix=c.helix,
            offset=c.offset,
        )
    if not report.acceptable:
        yield Violation(
            rule="crossover_azimuth",
            severity=Severity.VIOLATION,
            message=(
                f"rms phasing strain {report.rms_deg:.0f} deg over {len(report.crossovers)} "
                f"crossovers, above {azimuth.MAX_RMS_DEG:.0f}; published designs score 18-22"
            ),
        )
    if report.carries_twist:
        yield Violation(
            rule="crossover_azimuth",
            severity=Severity.WARNING,
            message=(
                f"helices carry {report.accumulated_twist_deg:.0f} deg of uncorrected twist "
                f"({report.twist_deg_per_bp:+.2f} deg/bp); intended only in a twist control"
            ),
        )


def check_staple_length(design: sc.Design) -> Iterator[Violation]:
    low, high = STAPLE_LENGTH_NT
    want_low, want_high = STAPLE_LENGTH_TARGET_NT
    for staple in ad.staples(design):
        helix, offset = _staple_anchor(staple)
        n = staple.dna_length()
        if not (low <= n <= high):
            yield Violation(
                "staple_length",
                Severity.VIOLATION,
                f"staple is {n} nt, outside {low}-{high}",
                helix,
                offset,
            )
        elif not (want_low <= n <= want_high):
            yield Violation(
                "staple_length",
                Severity.WARNING,
                f"staple is {n} nt, outside the {want_low}-{want_high} target band",
                helix,
                offset,
            )


def check_seed_domain(design: sc.Design) -> Iterator[Violation]:
    """Every staple needs one long domain to nucleate on.

    Without a continuous stretch this long, a staple has nothing that binds
    stably at folding temperature and tends not to incorporate at all.
    """
    for staple in ad.staples(design):
        helix, offset = _staple_anchor(staple)
        longest = max((d.dna_length() for d in staple.domains if hasattr(d, "helix")), default=0)
        if longest < STAPLE_SEED_DOMAIN_NT:
            yield Violation(
                "seed_domain",
                Severity.VIOLATION,
                f"longest domain is {longest} nt, under the {STAPLE_SEED_DOMAIN_NT} nt seed",
                helix,
                offset,
            )


def check_min_domain(design: sc.Design) -> Iterator[Violation]:
    for staple in ad.staples(design):
        for domain in staple.domains:
            if not hasattr(domain, "helix"):
                continue
            n = domain.dna_length()
            if n < STAPLE_MIN_DOMAIN_NT:
                yield Violation(
                    "min_domain",
                    Severity.VIOLATION,
                    f"domain is {n} nt, under the {STAPLE_MIN_DOMAIN_NT} nt floor",
                    domain.helix,
                    domain.start,
                )


def check_sandwich(design: sc.Design) -> Iterator[Violation]:
    """Short-long-short staples: a long grip with two weak ends.

    Defined here as three domains whose outer two are both under the seed
    length while the middle one is at or above it. Those ends melt first, and
    the staple hangs on by its middle while doing nothing useful at the edges.
    A preference, not a hard rule: published designs contain them.
    """
    for staple in ad.staples(design):
        domains = [d for d in staple.domains if hasattr(d, "helix")]
        if len(domains) != 3:
            continue
        first, middle, last = (d.dna_length() for d in domains)
        weak_ends = first < STAPLE_SEED_DOMAIN_NT and last < STAPLE_SEED_DOMAIN_NT
        if weak_ends and middle >= STAPLE_SEED_DOMAIN_NT:
            helix, offset = _staple_anchor(staple)
            yield Violation(
                "sandwich",
                Severity.WARNING,
                f"sandwich staple {first}-{middle}-{last} nt",
                helix,
                offset,
            )


def check_crossover_clearance(design: sc.Design) -> Iterator[Violation]:
    """A staple crossover too close to a scaffold one strains the junction.

    Only crossovers on the SAME pair of helices are compared: two crossovers at
    the same offset on unrelated helix pairs are nowhere near each other.
    """
    scaffold = design.scaffold
    if scaffold is None:
        return
    scaffold_points: dict[frozenset[int], list[int]] = {}
    for pair, offset in _crossovers(scaffold):
        scaffold_points.setdefault(pair, []).append(offset)

    for staple in ad.staples(design):
        for pair, offset in _crossovers(staple):
            for other in scaffold_points.get(pair, ()):
                gap = abs(offset - other)
                if gap < STAPLE_CROSSOVER_CLEARANCE_BP:
                    a, b = sorted(pair)
                    yield Violation(
                        "crossover_clearance",
                        Severity.VIOLATION,
                        f"staple crossover {gap} bp from a scaffold crossover "
                        f"on helices {a}/{b} (needs {STAPLE_CROSSOVER_CLEARANCE_BP})",
                        a,
                        offset,
                    )
                    break


def check_poly_g(design: sc.Design) -> Iterator[Violation]:
    """Long G runs form quadruplexes and synthesise badly."""
    pattern = re.compile(f"G{{{POLY_G_RUN_FLAG},}}")
    for staple in ad.staples(design):
        sequence = staple.dna_sequence
        if not sequence:
            continue
        helix, offset = _staple_anchor(staple)
        for match in pattern.finditer(sequence.upper()):
            yield Violation(
                "poly_g",
                Severity.WARNING,
                f"poly-G run of {len(match.group())} at position {match.start()} in the staple",
                helix,
                offset,
            )


RULES: Sequence[Rule] = (
    Rule("staple_length", f"staple length within {STAPLE_LENGTH_NT}", check_staple_length),
    Rule("seed_domain", f"one domain of at least {STAPLE_SEED_DOMAIN_NT} nt", check_seed_domain),
    Rule("min_domain", f"no domain under {STAPLE_MIN_DOMAIN_NT} nt", check_min_domain),
    Rule("sandwich", "no short-long-short staples", check_sandwich),
    Rule(
        "crossover_clearance",
        f"staple crossovers at least {STAPLE_CROSSOVER_CLEARANCE_BP} bp from scaffold ones",
        check_crossover_clearance,
    ),
    Rule("poly_g", f"no poly-G runs of {POLY_G_RUN_FLAG} or more", check_poly_g),
    Rule(
        "crossover_azimuth",
        "every crossover made where the backbone faces its partner",
        check_crossover_azimuth,
    ),
)

#: Declared but not implemented, and named so it is not mistaken for passing.
#: "Strong predicted self-structure" needs a thermodynamics backend, which is
#: the `thermo` extra and is not built yet. Reporting it as skipped beats
#: reporting a clean design that was never checked.
UNIMPLEMENTED: Sequence[tuple[str, str]] = (
    ("self_structure", "needs a thermodynamics backend (the `thermo` extra); not implemented"),
)


@dataclass(frozen=True)
class LintReport:
    violations: tuple[Violation, ...]

    @property
    def hard(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.VIOLATION)

    @property
    def warnings(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        """Warnings do not fail a design; hard constraints do."""
        return not self.hard

    def counts_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in self.violations:
            counts[v.rule] = counts.get(v.rule, 0) + 1
        return dict(sorted(counts.items()))

    def as_dict(self, *, limit: int | None = None) -> dict[str, Any]:
        shown = self.violations if limit is None else self.violations[:limit]
        return {
            "ok": self.ok,
            "counts": {"violations": len(self.hard), "warnings": len(self.warnings)},
            "by_rule": self.counts_by_rule(),
            "findings": [v.as_dict() for v in shown],
            "truncated": limit is not None and len(self.violations) > limit,
            "not_checked": [{"rule": n, "why": w} for n, w in UNIMPLEMENTED],
        }


def lint(design: sc.Design, *, only: Sequence[str] | None = None) -> LintReport:
    """Run every rule, or the named subset, and collect what they find."""
    selected = [r for r in RULES if only is None or r.name in only]
    if only is not None:
        unknown = set(only) - {r.name for r in RULES}
        if unknown:
            raise ValueError(f"unknown rule(s): {', '.join(sorted(unknown))}")
    found: list[Violation] = []
    for rule in selected:
        found.extend(rule.check(design))
    return LintReport(tuple(found))

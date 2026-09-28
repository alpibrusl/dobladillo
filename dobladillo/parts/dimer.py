"""Two E1 rectangles, A and B, that join end to end: E9's rectangle dimer.

Each is folded on its own, purified, and then the two are mixed. A's `end`
edge carries eleven single-stranded sticky ends and B's `start` edge carries
their complements, so an A meets a B edge to edge and the pair reads on the
AFM as one sheet twice as long. Everything else about A and B is E1's
rectangle, staple for staple.

Sticky ends rather than stacking
--------------------------------
Two ways to glue origami edge to edge are published, and both were read before
choosing (all open access or public abstracts):

* **Blunt-end stacking.** Rectangles whose edges end in blunt helices stack
  "so strongly that they may form long chains over 5 microns in length"
  (Rothemund 2006, Supplementary Note S5.7). Woo & Rothemund 2011 made that
  specific -- shape-complementary or binary-coded patterns of blunt ends as
  orthogonal bonds. It needs no extra sequence, but a stacking bond is
  specific only through a pattern cut into both edges, it is the very
  interaction that makes plain rectangles polymerise, and nothing in this
  toolchain can predict its strength.
* **Watson-Crick sticky ends** on the edge staples, the mechanism of Zenk &
  Schulman 2016 (JACS; 75-80% yields, forward rate constants 1e5-1e6 /M/s),
  Liber et al. 2018 and Sheheade et al. 2019 (Small), Wang et al. 2025
  (Nat. Commun., PMC11696045: 11-nt sticky ends, 81-92% dimer yields by AFM)
  and the DNA-only control of Zou et al. 2023 (ACS Nano, PMC9835977: 5-nt
  sticky ends x10 gave 23%, x8 gave 7%, at 25 C for 12 h at 4 nM). Their
  strength is a hybridisation free energy, which `sequence.thermo` computes,
  and their specificity is checkable against everything else in the tube.

So: sticky ends, because this project can design and check them and cannot
design a stacking bond; the whole thermodynamic argument below is primer3's.

What the other edges do
-----------------------
Blunt ends are still there, and they are the enemy. Liber et al. 2018 found
dimer yields "never higher than 86%" and traced it to monomers self-dimerising
"likely via blunt-end interactions". Rothemund 2006 S5.7 gives two cures,
both shown to work: leave the edge staples out (the rectangle then has
unstructured scaffold along that edge), or add 4-T tails to the staples that
end on the edge -- on 3-hole disks, "just a small number (12) of 4T tails"
caused "almost complete disaggregation".

This design uses **4-T tails**, on every staple end that sits on an edge:

* the outer edges (A's `start`, B's `end`) get ``TTTT`` on both the 5' and the
  3' end of each of their 11 edge staples. scadnano's edge staple has its 5'
  end on one helix of a pair and its 3' end on the other, both at the edge, so
  two tails cover all 22 helix ends of that edge.
* the mating edges get ``TTTT`` on the 5' end and the sticky end on the 3'
  end, so no helix end on either edge is left blunt.

Omitting the outer edge staples instead (`outer="omit"`) is supported and
free, and was not chosen for two reasons: it leaves 22 x 16 = 352 nt of
single-stranded scaffold on each outer edge for the sticky ends to find
(`scaffold_single_strands` includes it in the checks when it is there), and it
shortens the monomer by one 16-bp column, so A and B would no longer have
E1's measured footprint. `outer="blunt"` keeps E1's plain edge staples: the
stacking control, which should polymerise.

The sticky ends
---------------
Where: every one of the 11 edge staples on each mating edge. scadnano's
rectangle puts the 3' ends of A's `end`-edge staples on the odd helices and of
B's `start`-edge staples on the even helices, so sticky end k joins A's helix
2k+1 to B's helix 2k. Spreading eleven bonds along the whole 66 nm edge,
rather than a few, is what keeps the joint from pivoting, and a dimer that
lies straight on mica is one the footprint classifier can recognise.

Each 3' extension is ``TT`` + a 12-nt sticky sequence. The ``TT`` is a
spacer: the two halves of a bond hang from adjacent helices, 2.6 nm apart, and
without it the bridging duplex would have to shear the helix ends to form.
That number is geometry, not literature.

How long, and which sequences, is decided by four conditions at the mixing
buffer, all computed by primer3 (`check_sticky_ends`):

1. **Intended bond**: each sticky end on its own melts at or above the mixing
   temperature plus 5 C, at the mixing concentration. A contact that is more
   often formed than not can zip the rest of the edge; one that melts far
   below the mixing temperature is Zou's 5-nt case. An 11-nt, 50%-GC sticky
   end computes to about 30 C here, which is where Wang's 11-nt ends sit.
2. **No unintended pairing** between any two extensions -- A with A (a
   homodimer), B with B, a sticky end with a non-partner (a mis-registered
   dimer), any strand with itself -- and no hairpin: every such structure
   melts below 0 C, colder than any step the sample sees.
3. **No staple cross-binding**: against every staple of the design, at the
   folding staple concentration (50 nM), below the mixing temperature minus
   10 C. A sticky end sits in that staple excess until purification.
4. **No scaffold cross-binding**: against every single-stranded stretch of
   scaffold -- the 319-nt loop every monomer carries -- below 0 C at the
   mixing concentration. A sticky end that finds another monomer's loop makes
   a cross-link no purification removes.

The sequences are searched deterministically (`design_sticky_ends`) and
pinned in `STICKY_ENDS`; a test re-runs the search. **12 nt is the shortest
length that passes**: in 50,000 candidates the search finds no set member at
10 nt and three at 11 nt, where eleven are needed; at 12 nt it finds eleven
(the pinned set). Measured with this module on 2026-09-28, not taken from a
paper. At 12 nt the weakest sticky end melts at 30.1 C alone and the
strongest at 36.9 C, at 2 nM and 11 mM free magnesium.

What this module does not establish
------------------------------------
Whether the bridge's geometry lets all eleven bonds form at once; the rate;
and the yield. A predicted Tm is a design ordering at a von Ahsen salt
equivalent (see `sequence.thermo.SALT_NOTE`), not a calibrated value. E9
measures the yield; nothing here predicts it.

References: Rothemund, Nature 440, 297 (2006) and its Supplementary Notes
(S5.7); Woo & Rothemund, Nat. Chem. 3, 620 (2011); Zenk, Tuntivate &
Schulman, JACS 138, 3346 (2016); Liber et al., Small 14, e1800218 (2018);
Sheheade et al., Small 15, e1902979 (2019); Zou et al., ACS Nano 17, 752
(2023); Wang et al., Nat. Commun. 16, 263 (2025).
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal

from dobladillo import _scadnano as ad
from dobladillo.constants import BUFFER_EDTA_MM
from dobladillo.interfaces import Bond, Brick, crosstalk, unsatisfied
from dobladillo.parts.rectangle import COLUMN_NT, Rectangle, rothemund_rectangle
from dobladillo.sequence.thermo import (
    Hybrid,
    hairpin,
    hybrid,
    is_self_complementary,
    reverse_complement,
)

if TYPE_CHECKING:
    import scadnano as sc

Edge = Literal["start", "end"]
Outer = Literal["poly_t", "omit", "blunt"]

#: The scaffold E1 is folded from. Stated here, and passed to the rectangle
#: explicitly, because the extended staples force a second scaffold assignment
#: and it must be the same one; `test_dimer` checks A and B's unmodified
#: staples are E1's, which would catch a mismatch.
SCAFFOLD_VARIANT: Final = "p7249"
SCAFFOLD_ROTATION: Final = 5587

#: Passivating tail on staple ends that sit on an edge. Rothemund 2006 S5.7.
POLY_T: Final = "TTTT"

#: Unpaired bases between a mating staple's 3' end and its sticky sequence.
SPACER: Final = "TT"

#: Sticky length and count. See the module docstring for why 12 and 11.
DEFAULT_STICKY_NT: Final = 12
EDGE_STAPLES: Final = 11

#: The sticky-end sequences on A's `end` edge, bottom helix pair first. B
#: carries their reverse complements. Output of `design_sticky_ends()` with
#: its defaults; a test re-runs the search and must reproduce it.
STICKY_ENDS: Final[tuple[str, ...]] = (
    "AACACATGACGA",
    "CTAGGACCTTCA",
    "AGTGGATGTAGG",
    "TTCCCTTAGTGT",
    "CTCTTAGTCTGC",
    "TGCTTACTCCAT",
    "TTGGACAAGATG",
    "TCTAGTGTACCC",
    "GGAGATGTCTGT",
    "ATGCTAAGATCG",
    "AGACTTAACACG",
)

#: The channel the sticky pair is declared on. Channel 0 is every rectangle's
#: default, so an assembly that also used plain rectangles would not collide.
STICKY_CHANNEL: Final = 1


@dataclass(frozen=True)
class Conditions:
    """The buffer and concentrations the sticky ends are designed for.

    The nominal magnesium is not E1's result -- E1 has not run. 12 mM is the
    middle of the screen, the same design value as the hinge ladder's. The
    free magnesium is the nominal minus the folding buffer's 1 mM EDTA, which
    binds it one to one (`experiments/protocols/common-techniques.md` s1).
    Tris is not counted as a counterion: next to 120 x sqrt(11) = 398 mM of
    sodium equivalent, 5 mM of it moves nothing.
    """

    magnesium_nominal_mm: float = 12.0
    mixing_temperature_c: float = 25.0
    #: Each monomer, in the mix. Each sticky end is at this concentration.
    monomer_nm: float = 2.0
    #: Each staple, in the folding reaction (5x over 10 nM scaffold).
    folding_staple_nm: float = 50.0

    @property
    def magnesium_free_m(self) -> float:
        return max(self.magnesium_nominal_mm - BUFFER_EDTA_MM, 0.0) / 1000.0

    #: Condition 1: the lowest Tm an intended sticky end may have.
    @property
    def intended_min_tm_c(self) -> float:
        return self.mixing_temperature_c + 5.0

    #: Condition 3: the highest Tm a sticky end may have against a staple.
    @property
    def staple_max_tm_c(self) -> float:
        return self.mixing_temperature_c - 10.0

    #: Conditions 2 and 4.
    unintended_max_tm_c: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "magnesium_nominal_mm": self.magnesium_nominal_mm,
            "magnesium_free_mm": round(self.magnesium_free_m * 1000.0, 3),
            "edta_mm": BUFFER_EDTA_MM,
            "mixing_temperature_c": self.mixing_temperature_c,
            "monomer_nm": self.monomer_nm,
            "folding_staple_nm": self.folding_staple_nm,
            "intended_min_tm_c": self.intended_min_tm_c,
            "unintended_max_tm_c": self.unintended_max_tm_c,
            "staple_max_tm_c": self.staple_max_tm_c,
            "salt_model": "primer3 thal, von Ahsen Na equivalent; a design ordering, "
            "not a calibrated value (sequence.thermo.SALT_NOTE)",
        }


DEFAULT_CONDITIONS: Final = Conditions()


# ----------------------------------------------------------------- thermo


def _pair(first: str, second: str, conditions: Conditions, *, strand_nm: float) -> Hybrid:
    return hybrid(
        first,
        second,
        magnesium_m=conditions.magnesium_free_m,
        temperature_c=conditions.mixing_temperature_c,
        strand_m=strand_nm * 1e-9,
    )


def _windows(sequence: str, *, width: int = 60, step: int = 20) -> list[str]:
    """Overlapping windows no longer than primer3 aligns, covering every base."""
    if len(sequence) <= width:
        return [sequence] if len(sequence) >= 2 else []
    starts = list(range(0, len(sequence) - width + 1, step))
    if starts[-1] != len(sequence) - width:
        starts.append(len(sequence) - width)
    return [sequence[s : s + width] for s in starts]


def extension(sticky: str) -> str:
    """The 3' extension a mating staple carries: spacer, then sticky end."""
    return SPACER + sticky


@dataclass(frozen=True)
class Finding:
    """One condition, its worst case, and whether it held."""

    condition: str
    limit_c: float
    worst: Hybrid | None
    passed: bool
    checked: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "limit_c": self.limit_c,
            "passed": self.passed,
            "checked": self.checked,
            "worst": self.worst.as_dict() if self.worst else None,
        }


@dataclass(frozen=True)
class StickyReport:
    """Every thermodynamic check on a set of sticky ends, worst case first."""

    sticky: tuple[str, ...]
    conditions: Conditions
    intended: tuple[Hybrid, ...]
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return all(f.passed for f in self.findings)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(
            f"{f.condition}: {f.worst.first} x {f.worst.second} melts at "
            f"{f.worst.melting_c:.1f} C against a limit of {f.limit_c:.1f} C"
            for f in self.findings
            if not f.passed and f.worst is not None
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "sticky_ends": list(self.sticky),
            "conditions": self.conditions.as_dict(),
            "intended": [h.as_dict() for h in self.intended],
            "findings": [f.as_dict() for f in self.findings],
            "passed": self.passed,
            "failures": list(self.failures),
        }


def _worst(hybrids: list[Hybrid]) -> Hybrid | None:
    return max(hybrids, key=lambda h: h.melting_c) if hybrids else None


def _unintended_pairs(sticky: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every pair of extensions that must NOT bind, including self-pairs.

    The set in the tube: A's sticky extensions, B's complementary ones, and the
    poly-T tails. Only (A_k, B_k) is intended.
    """
    a = [extension(s) for s in sticky]
    b = [extension(reverse_complement(s)) for s in sticky]
    strands = [*a, *b, POLY_T]
    intended = {frozenset((a[k], b[k])) for k in range(len(sticky))}
    pairs = []
    for x, y in itertools.combinations_with_replacement(strands, 2):
        if frozenset((x, y)) in intended:
            continue
        pairs.append((x, y))
    return pairs


def check_sticky_ends(
    sticky: tuple[str, ...],
    *,
    staples: tuple[str, ...],
    single_strands: tuple[str, ...],
    conditions: Conditions = DEFAULT_CONDITIONS,
) -> StickyReport:
    """The four conditions of the module docstring, each with its worst case.

    `staples` are every staple of both components (their bound parts are E1's
    staples; extensions are checked separately, as pairs). `single_strands`
    are the scaffold stretches no staple covers.
    """
    for s in sticky:
        if is_self_complementary(s):
            raise ValueError(
                f"sticky end {s} is self-complementary: every copy binds every other, so A "
                "dimerises with A and B with B as readily as A with B"
            )
    # Two sticky ends that are each other's complement put both halves of one
    # bond on the SAME edge, so A self-dimerises -- the mechanism Liber et al.
    # 2018 blamed for yields never above 86%, arrived at by design instead of
    # by accident. It is refused rather than reported, because the pair-by-pair
    # check below cannot see it: (A_j, B_k) with sticky_j complementary to
    # sticky_k is the same pair of strands as the intended (A_j, B_j).
    for j, k in itertools.combinations(range(len(sticky)), 2):
        if sticky[j] == sticky[k] or sticky[j] == reverse_complement(sticky[k]):
            raise ValueError(
                f"sticky ends {j} ({sticky[j]}) and {k} ({sticky[k]}) are the same bond: "
                "both halves of it would sit on A's edge, which self-dimerises"
            )
    intended = tuple(
        _pair(
            extension(s),
            extension(reverse_complement(s)),
            conditions,
            strand_nm=conditions.monomer_nm,
        )
        for s in sticky
    )
    bare = [
        _pair(s, reverse_complement(s), conditions, strand_nm=conditions.monomer_nm) for s in sticky
    ]
    weakest = min(bare, key=lambda h: h.melting_c) if bare else None
    findings = [
        Finding(
            condition="intended bond: weakest sticky end, alone",
            limit_c=conditions.intended_min_tm_c,
            worst=weakest,
            passed=weakest is not None and weakest.melting_c >= conditions.intended_min_tm_c,
            checked=len(bare),
        )
    ]

    pairs = [
        _pair(x, y, conditions, strand_nm=conditions.monomer_nm)
        for x, y in _unintended_pairs(sticky)
    ]
    worst = _worst(pairs)
    findings.append(
        Finding(
            condition="unintended pairing between extensions",
            limit_c=conditions.unintended_max_tm_c,
            worst=worst,
            passed=worst is None or worst.melting_c < conditions.unintended_max_tm_c,
            checked=len(pairs),
        )
    )

    ends = [extension(s) for s in sticky] + [extension(reverse_complement(s)) for s in sticky]
    hairpins = [
        hairpin(
            e,
            magnesium_m=conditions.magnesium_free_m,
            temperature_c=conditions.mixing_temperature_c,
        )
        for e in ends
    ]
    worst = _worst(hairpins)
    findings.append(
        Finding(
            condition="hairpin within an extension",
            limit_c=conditions.unintended_max_tm_c,
            worst=worst,
            passed=worst is None or worst.melting_c < conditions.unintended_max_tm_c,
            checked=len(hairpins),
        )
    )

    against = [
        _pair(e, staple, conditions, strand_nm=conditions.folding_staple_nm)
        for e in ends
        for staple in staples
    ]
    worst = _worst(against)
    findings.append(
        Finding(
            condition="staple cross-binding, at the folding staple concentration",
            limit_c=conditions.staple_max_tm_c,
            worst=worst,
            passed=worst is None or worst.melting_c < conditions.staple_max_tm_c,
            checked=len(against),
        )
    )

    windows = [w for s in single_strands for w in _windows(s)]
    scaffold = [
        _pair(e, w, conditions, strand_nm=conditions.monomer_nm) for e in ends for w in windows
    ]
    worst = _worst(scaffold)
    findings.append(
        Finding(
            condition="single-stranded scaffold cross-binding",
            limit_c=conditions.unintended_max_tm_c,
            worst=worst,
            passed=worst is None or worst.melting_c < conditions.unintended_max_tm_c,
            checked=len(scaffold),
        )
    )
    return StickyReport(
        sticky=tuple(sticky), conditions=conditions, intended=intended, findings=tuple(findings)
    )


# ----------------------------------------------------------------- search

#: Composition rules for a candidate, before any thermodynamics: GC between 40
#: and 60%, no run of four of one base (synthesis, and G-quadruplexes; see
#: constants.POLY_G_RUN_FLAG), not self-complementary.
_GC_RANGE: Final = (0.4, 0.6)
_MAX_RUN: Final = 3


def candidate(index: int, *, length: int, seed: int = 0) -> str:
    """The `index`-th candidate sequence, from a hash rather than an RNG.

    A seeded random generator is reproducible only as long as its algorithm
    is; SHA-256 of a counter is reproducible forever, which is what a pinned
    sequence list needs to be regenerated years from now.
    """
    out = ""
    block = 0
    while len(out) < length:
        digest = hashlib.sha256(f"dobladillo-sticky:{seed}:{index}:{block}".encode()).digest()
        out += "".join("ACGT"[(byte >> shift) & 3] for byte in digest for shift in (6, 4, 2, 0))
        block += 1
    return out[:length]


def _composition_ok(sequence: str) -> bool:
    gc = sum(b in "GC" for b in sequence) / len(sequence)
    if not _GC_RANGE[0] <= gc <= _GC_RANGE[1]:
        return False
    if any(b * (_MAX_RUN + 1) in sequence for b in "ACGT"):
        return False
    return not is_self_complementary(sequence)


def design_sticky_ends(
    *,
    count: int = EDGE_STAPLES,
    length: int = DEFAULT_STICKY_NT,
    staples: tuple[str, ...],
    single_strands: tuple[str, ...],
    conditions: Conditions = DEFAULT_CONDITIONS,
    seed: int = 0,
    max_candidates: int = 50_000,
) -> tuple[str, ...]:
    """Greedily pick `count` sticky ends that pass all four conditions.

    Candidates are tried in a fixed order; each is kept if, together with the
    ones already kept, every condition still holds. Greedy is not optimal and
    need not be: the question is whether a passing set exists at this length,
    and the answer is reproducible.
    """
    c = conditions
    limit = c.unintended_max_tm_c
    windows = [w for s in single_strands for w in _windows(s)]

    def cold(x: str, y: str, *, strand_nm: float = c.monomer_nm, below: float = limit) -> bool:
        return _pair(x, y, c, strand_nm=strand_nm).melting_c < below

    def alone(s: str) -> bool:
        if _pair(s, reverse_complement(s), c, strand_nm=c.monomer_nm).melting_c < (
            c.intended_min_tm_c
        ):
            return False
        a, b = extension(s), extension(reverse_complement(s))
        if any(
            hairpin(
                e, magnesium_m=c.magnesium_free_m, temperature_c=c.mixing_temperature_c
            ).melting_c
            >= limit
            for e in (a, b)
        ):
            return False
        return all(cold(x, y) for x, y in ((a, a), (b, b), (a, POLY_T), (b, POLY_T)))

    def with_set(s: str) -> bool:
        mine = (extension(s), extension(reverse_complement(s)))
        return all(
            cold(x, y)
            for other in chosen
            for x in mine
            for y in (extension(other), extension(reverse_complement(other)))
        )

    def kmers(sequence: str, k: int = 5) -> set[str]:
        return {sequence[i : i + k] for i in range(len(sequence) - k + 1)}

    staple_kmers = [(staple, kmers(staple)) for staple in staples]

    def background(s: str) -> bool:
        mine = (extension(s), extension(reverse_complement(s)))
        for e in mine:
            # Most candidates fail on one staple they share a long complement
            # with. Asking primer3 about those first makes the failure cheap;
            # every staple is still asked before a candidate is accepted.
            target = kmers(reverse_complement(e))
            ordered = sorted(staple_kmers, key=lambda item: -len(item[1] & target))
            if not all(
                cold(e, staple, strand_nm=c.folding_staple_nm, below=c.staple_max_tm_c)
                for staple, _ in ordered
            ):
                return False
        return all(cold(e, w) for e in mine for w in windows)

    # The same conditions as `check_sticky_ends`, applied one candidate at a
    # time against the set so far, cheapest first. The finished set is then
    # checked whole, by the function the tests use.
    chosen: list[str] = []
    for index in range(max_candidates):
        s = candidate(index, length=length, seed=seed)
        if not _composition_ok(s) or s in chosen or reverse_complement(s) in chosen:
            continue
        if not (alone(s) and with_set(s) and background(s)):
            continue
        chosen.append(s)
        if len(chosen) == count:
            report = check_sticky_ends(
                tuple(chosen), staples=staples, single_strands=single_strands, conditions=c
            )
            if not report.passed:  # pragma: no cover - the two must agree
                raise AssertionError(f"incremental search disagrees: {report.failures}")
            return tuple(chosen)
    raise ValueError(
        f"found only {len(chosen)} of {count} sticky ends of {length} nt in "
        f"{max_candidates} candidates; try a longer sticky end"
    )


# ----------------------------------------------------------------- the part


@dataclass(frozen=True)
class EdgeStaple:
    """One of the rectangle's edge staples, and what this design hangs on it."""

    component: str
    edge: Edge
    #: The helix its 3' end sits on, which is where a 3' extension hangs.
    helix_3p: int
    #: E1's staple, unchanged: the part bound to the scaffold.
    core: str
    five_prime: str
    three_prime: str
    role: Literal["sticky", "passivated", "plain"]
    #: Index into the sticky set, for a sticky staple.
    pair: int | None = None

    @property
    def sequence(self) -> str:
        return self.five_prime + self.core + self.three_prime

    def as_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "edge": self.edge,
            "helix_3p": self.helix_3p,
            "role": self.role,
            "pair": self.pair,
            "five_prime": self.five_prime,
            "core": self.core,
            "three_prime": self.three_prime,
            "sequence": self.sequence,
            "length_nt": len(self.sequence),
        }


@dataclass(frozen=True)
class Component:
    """A or B: the E1 rectangle with one edge made sticky and one passivated."""

    name: str
    design: sc.Design
    helices: int
    length: int
    mating_edge: Edge
    outer_edge: Edge
    #: Every edge staple this component changed or removed; the rest are E1's.
    modified: tuple[EdgeStaple, ...]
    #: E1 edge staples this component leaves out (outer="omit").
    omitted: tuple[str, ...]
    scaffold: ad.ScaffoldAccounting

    @property
    def staple_sequences(self) -> frozenset[str]:
        return frozenset(s.dna_sequence or "" for s in ad.staples(self.design))

    @property
    def extra(self) -> tuple[EdgeStaple, ...]:
        """Staples that are not E1's: everything carrying an extension."""
        return tuple(s for s in self.modified if s.role != "plain")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mating_edge": self.mating_edge,
            "outer_edge": self.outer_edge,
            "staple_count": len(ad.staples(self.design)),
            "extra_staples": len(self.extra),
            "omitted_e1_staples": len(self.omitted),
            "scaffold": self.scaffold.as_dict(),
        }


def _edge_staples(design: sc.Design, *, length: int) -> dict[Edge, list[sc.Strand]]:
    """The staples lying entirely in the first or the last 16-bp column.

    scadnano's rectangle draws exactly one staple per helix pair there, with
    both its 5' and its 3' end on the edge; this is checked rather than
    assumed, because a 3' extension that did not start at the edge would hang
    into the sheet.
    """
    found: dict[Edge, list[sc.Strand]] = {"start": [], "end": []}
    for strand in ad.staples(design):
        bound = [d for d in strand.domains if hasattr(d, "helix")]
        low = min(d.start for d in bound)
        high = max(d.end for d in bound)
        if high <= COLUMN_NT:
            edge: Edge = "start"
        elif low >= length - COLUMN_NT:
            edge = "end"
        else:
            continue
        last = bound[-1]
        three_offset = last.end - 1 if last.forward else last.start
        first = bound[0]
        five_offset = first.start if first.forward else first.end - 1
        at = 0 if edge == "start" else length - 1
        if three_offset != at or five_offset != at:
            raise AssertionError(
                f"edge staple on helices {[d.helix for d in bound]} does not end on the "
                f"{edge} edge; scadnano's rectangle layout changed"
            )
        found[edge].append(strand)
    for strands in found.values():
        strands.sort(key=lambda s: [d for d in s.domains if hasattr(d, "helix")][-1].helix)
    return found


def _helix_3p(strand: sc.Strand) -> int:
    return int([d for d in strand.domains if hasattr(d, "helix")][-1].helix)


def single_stranded_scaffold(design: sc.Design, *, variant: str, rotation: int) -> tuple[str, ...]:
    """Every stretch of scaffold no staple pairs with, 5' to 3'.

    The unrouted loop (the tail of the rotated scaffold past what the routing
    uses) and, for `outer="omit"`, the bare edge columns. These are what a
    sticky end on another monomer can find.
    """
    covered: set[tuple[int, int]] = set()
    for strand in ad.staples(design):
        for d in strand.domains:
            if hasattr(d, "helix"):
                covered.update((d.helix, o) for o in range(d.start, d.end))
    scaffold = ad.scaffold_strand(design)
    sequence = scaffold.dna_sequence or ""
    runs: list[str] = []
    current = ""
    index = 0
    for d in scaffold.domains:
        if not hasattr(d, "helix"):
            continue
        offsets = range(d.start, d.end) if d.forward else range(d.end - 1, d.start - 1, -1)
        for offset in offsets:
            if offset in d.deletions:
                continue
            if (d.helix, offset) in covered:
                if current:
                    runs.append(current)
                current = ""
            else:
                current += sequence[index]
            index += 1
    if current:
        runs.append(current)
    full = ad.scaffold_sequence(variant, rotation=rotation)
    loop = full[len(sequence) :]
    return tuple(r for r in (*runs, loop) if r)


def _component(
    name: str,
    *,
    mating: Edge,
    sticky: tuple[str, ...],
    outer: Outer,
) -> Component:
    rectangle = rothemund_rectangle(
        scaffold_variant=SCAFFOLD_VARIANT, scaffold_rotation=SCAFFOLD_ROTATION
    )
    design = rectangle.design
    other: Edge = "start" if mating == "end" else "end"
    edges = _edge_staples(design, length=rectangle.length)
    if len(edges[mating]) != len(sticky):
        raise ValueError(
            f"{len(sticky)} sticky ends for {len(edges[mating])} edge staples on the "
            f"{mating} edge; one per edge staple"
        )

    plan: list[tuple[sc.Strand, EdgeStaple]] = []
    omitted: list[str] = []
    for k, strand in enumerate(edges[mating]):
        end = sticky[k] if name == "A" else reverse_complement(sticky[k])
        plan.append(
            (
                strand,
                EdgeStaple(
                    component=name,
                    edge=mating,
                    helix_3p=_helix_3p(strand),
                    core=strand.dna_sequence or "",
                    five_prime=POLY_T,
                    three_prime=extension(end),
                    role="sticky",
                    pair=k,
                ),
            )
        )
    for strand in edges[other]:
        if outer == "omit":
            omitted.append(strand.dna_sequence or "")
            design.remove_strand(strand)
        elif outer == "poly_t":
            plan.append(
                (
                    strand,
                    EdgeStaple(
                        component=name,
                        edge=other,
                        helix_3p=_helix_3p(strand),
                        core=strand.dna_sequence or "",
                        five_prime=POLY_T,
                        three_prime=POLY_T,
                        role="passivated",
                    ),
                )
            )

    replaced = [
        (
            ad.replace_with_extensions(
                design,
                strand,
                five_prime_nt=len(spec.five_prime),
                three_prime_nt=len(spec.three_prime),
            ),
            spec,
        )
        for strand, spec in plan
    ]
    # The new strands' bound domains have no sequence yet; this re-derives
    # every staple from the scaffold, then the extensions are filled in.
    ad.assign_scaffold_sequence(design, variant=SCAFFOLD_VARIANT, rotation=SCAFFOLD_ROTATION)
    for strand, spec in replaced:
        ad.assign_end_extensions(
            design, strand, five_prime=spec.five_prime, three_prime=spec.three_prime
        )
        if strand.dna_sequence != spec.sequence:
            raise AssertionError(
                f"{name} staple at helix {spec.helix_3p} came out as {strand.dna_sequence}, "
                f"expected {spec.sequence}: the second scaffold assignment differs from E1's"
            )

    return Component(
        name=name,
        design=design,
        helices=rectangle.helices,
        length=rectangle.length,
        mating_edge=mating,
        outer_edge=other,
        modified=tuple(spec for _, spec in plan),
        omitted=tuple(omitted),
        scaffold=ad.ScaffoldAccounting(
            variant=SCAFFOLD_VARIANT,
            total_nt=rectangle.scaffold.total_nt,
            routed_nt=ad.scaffold_strand(design).dna_length(),
            deletions=rectangle.scaffold.deletions,
        ),
    )


@dataclass(frozen=True)
class Dimer:
    """A and B, the E1 rectangle they are made from, and their interface."""

    a: Component
    b: Component
    base: Rectangle
    sticky: tuple[str, ...]
    outer: Outer
    conditions: Conditions
    channel: int = STICKY_CHANNEL
    _report: list[StickyReport] = field(default_factory=list, repr=False, compare=False)

    # ------------------------------------------------------------ interface

    def bricks(self, *, channel_b: int | None = None) -> dict[str, Brick]:
        """A and B as bricks. Only the mating edges are ports.

        A passivated edge is not an interface -- that is what the tails are
        for -- so it is not declared, and `crosstalk` then has nothing to
        report. `channel_b` exists to show what a mis-assigned channel does.
        """
        rect_a = self.base.brick(channel=self.channel)
        rect_b = self.base.brick(channel=self.channel if channel_b is None else channel_b)
        return {
            "A": Brick(
                name="rectangle-dimer-A",
                ports=tuple(p for p in rect_a.ports if p.name == self.a.mating_edge),
            ),
            "B": Brick(
                name="rectangle-dimer-B",
                ports=tuple(p for p in rect_b.ports if p.name == self.b.mating_edge),
            ),
        }

    @property
    def bond(self) -> Bond:
        return Bond(
            left="A", left_port=self.a.mating_edge, right="B", right_port=self.b.mating_edge
        )

    def interface_problems(self) -> dict[str, list[str]]:
        bricks = self.bricks()
        return {
            "crosstalk": [str(c.as_dict()) for c in crosstalk(bricks, (self.bond,))],
            "unsatisfied": list(unsatisfied(bricks, (self.bond,))),
        }

    # ------------------------------------------------------------ geometry

    @property
    def monomer_nm(self) -> tuple[float, float]:
        """E1's footprint, less a column per omitted edge."""
        length, width = self.base.dimensions_nm
        if self.outer == "omit":
            length -= COLUMN_NT * float(ad.GEOMETRY.rise_per_base_pair)
        return (length, width)

    @property
    def gap_nm(self) -> float:
        """The bridge between the two edges, taken as the sticky duplex, straight.

        A rough figure: the spacers add up to ~2.4 nm if stretched and the
        duplex need not lie along the axis. It moves the dimer's predicted
        length by 2%, well inside the classifier's tolerance.
        """
        return len(self.sticky[0]) * float(ad.GEOMETRY.rise_per_base_pair)

    @property
    def dimer_length_nm(self) -> float:
        return 2 * self.monomer_nm[0] + self.gap_nm

    # ------------------------------------------------------------ checks

    def staples(self) -> tuple[str, ...]:
        """Every staple's bound part, both components: what a sticky end meets."""
        cores = {s.dna_sequence or "" for s in ad.staples(self.base.design)}
        return tuple(sorted(cores))

    def single_strands(self) -> tuple[str, ...]:
        runs: set[str] = set()
        for component in (self.a, self.b):
            runs.update(
                single_stranded_scaffold(
                    component.design, variant=SCAFFOLD_VARIANT, rotation=SCAFFOLD_ROTATION
                )
            )
        return tuple(sorted(runs))

    def report(self) -> StickyReport:
        """The thermodynamic checks. About a second; computed once."""
        if not self._report:
            self._report.append(
                check_sticky_ends(
                    self.sticky,
                    staples=self.staples(),
                    single_strands=self.single_strands(),
                    conditions=self.conditions,
                )
            )
        return self._report[0]

    def design_hash(self) -> str:
        """The assembly's identity: a hash over its two components' design hashes.

        Each component is hashed by `provenance.design_sha256`, under its
        scheme. The pair is then one node in the chain, so an order, a
        prediction and a scan can all name the same thing.
        """
        from dobladillo import provenance

        return provenance.json_sha256(
            {
                "assembly": "rectangle-dimer",
                "A": provenance.design_sha256(self.a.design),
                "B": provenance.design_sha256(self.b.design),
            }
        )

    def as_dict(self, *, with_report: bool = True) -> dict[str, Any]:
        length, width = self.monomer_nm
        out: dict[str, Any] = {
            "part": "dimer",
            "assembly": "two E1 rectangles joined end to end by sticky ends",
            "lattice": "square",
            "base": self.base.as_dict(),
            "outer_edges": self.outer,
            "components": {"A": self.a.as_dict(), "B": self.b.as_dict()},
            "sticky": {
                "count": len(self.sticky),
                "length_nt": len(self.sticky[0]),
                "spacer": SPACER,
                "sequences_on_A": list(self.sticky),
                "sequences_on_B": [reverse_complement(s) for s in self.sticky],
                "joins": "A helix 2k+1 to B helix 2k",
            },
            "poly_t": POLY_T,
            "channel": self.channel,
            "interface": self.interface_problems(),
            "approx_dimensions_nm": {
                "monomer_length": round(length, 1),
                "monomer_width": round(width, 1),
                "gap": round(self.gap_nm, 1),
                "dimer_length": round(self.dimer_length_nm, 1),
            },
            "scaffold": self.a.scaffold.as_dict(),
        }
        if with_report:
            out["thermodynamics"] = self.report().as_dict()
        return out


def rectangle_dimer(
    *,
    sticky: tuple[str, ...] = STICKY_ENDS,
    outer: Outer = "poly_t",
    conditions: Conditions = DEFAULT_CONDITIONS,
    channel: int = STICKY_CHANNEL,
) -> Dimer:
    """Build A and B from E1's rectangle.

    Does not run the thermodynamic checks -- `Dimer.report()` does, and the
    tests hold `STICKY_ENDS` to them -- so that building the part stays as
    cheap as building the rectangle.
    """
    if outer not in ("poly_t", "omit", "blunt"):
        raise ValueError(f"outer is poly_t, omit or blunt, got {outer!r}")
    sticky = tuple(s.upper() for s in sticky)
    if len({len(s) for s in sticky}) != 1:
        raise ValueError("every sticky end must be the same length")
    return Dimer(
        a=_component("A", mating="end", sticky=sticky, outer=outer),
        b=_component("B", mating="start", sticky=sticky, outer=outer),
        base=rothemund_rectangle(
            scaffold_variant=SCAFFOLD_VARIANT, scaffold_rotation=SCAFFOLD_ROTATION
        ),
        sticky=sticky,
        outer=outer,
        conditions=conditions,
        channel=channel,
    )


def search_inputs() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What `design_sticky_ends` checks candidates against, for poly-T edges.

    E1's staples, and the single-stranded scaffold of E1's rectangle -- the
    loop, since every edge is paired. That is the same scaffold A and B leave
    single-stranded with `outer="poly_t"` or `"blunt"`; with `"omit"` the bare
    edge columns add to it, and `Dimer.report()` checks those.
    """
    base = rothemund_rectangle(
        scaffold_variant=SCAFFOLD_VARIANT, scaffold_rotation=SCAFFOLD_ROTATION
    )
    staples = tuple(sorted({s.dna_sequence or "" for s in ad.staples(base.design)}))
    single = single_stranded_scaffold(
        base.design, variant=SCAFFOLD_VARIANT, rotation=SCAFFOLD_ROTATION
    )
    return staples, single

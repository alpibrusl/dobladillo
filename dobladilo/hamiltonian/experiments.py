"""The construct series for Stages 0 and 1, and what they cost to order.

HAMILTONIAN.md section 4 specifies both stages in prose. This turns that into a
counted list of constructs and oligos, because "about ten constructs" and "a
factorial reduced to about twenty" are the difference between a EUR 3k order
and a EUR 12k one, and the shared-core arithmetic is what decides which.

**The shared core is the whole economy of this.** A brick is roughly 200
staples and EUR 700 (`dobladilo lab order`). A series of ten independent
bricks would be EUR 7000. A series of ten variants that differ only in their
latch staples is one core plus ten small sets -- and the difference is what
makes a sweep affordable at all. `DESIGN.md` section 10 names this as the
mitigation for oligo cost; here it is arithmetic rather than an aspiration.

Two design decisions below come from this project's own power analysis rather
than from the source document, and both are flagged where they occur.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

#: Staples in the shared core of a single-hinge construct: everything except
#: the latches. Ordered once and reused by every variant in the stage.
CORE_STAPLES_SINGLE_HINGE = 200

#: And for a two-hinge plate, which is a larger object.
CORE_STAPLES_TWO_HINGE = 380

#: Staples that change when a latch changes: the latch itself and its partner,
#: plus the passivation around them.
LATCH_STAPLES = 12

#: Staples that change when a coupling strut changes.
STRUT_STAPLES = 8

#: From `lab.plates.DEFAULT_PRICE_PER_BASE`, at the 32 nt typical staple.
COST_PER_STAPLE_EUR = 3.2

#: A fluorophore-modified oligo costs roughly fifty times a plain one. NOT a
#: quote: dye, scale, purification and supplier all move it, and HPLC
#: purification is usually required for FRET work, which is most of the cost.
COST_PER_MODIFIED_OLIGO_EUR = 150.0

#: FRET pairs per construct, and whether they sit on the shared core.
#:
#: They do, and it is worth a sentence because it decides Stage 0's budget.
#: HAMILTONIAN.md section 3.1 puts the donor and acceptor **across the hinge
#: joint**, and the joint is core geometry, not latch. So the pair is ordered
#: ONCE for the whole series rather than once per construct. Two modified
#: oligos instead of twenty is EUR 300 instead of EUR 3000, which would
#: otherwise have tripled the stage.
FRET_OLIGOS_ON_CORE = 2

#: Tightened from the source document's ~1 kT. This project's noise-floor
#: measurement shows a designed 1 kT coupling comes back with a median error
#: near 0.85 kT when construct-to-construct scatter is 1 kT -- which fails
#: Stage 1's own requirement that J be constant to 0.3. See
#: `hamiltonian.discrepancy.noise_floor`.
STAGE0_SCATTER_GATE_KT = 0.3


@dataclass(frozen=True)
class Construct:
    """One thing to fold, and what makes it different from its siblings."""

    name: str
    varies: dict[str, Any]
    variant_staples: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "varies": self.varies, "variant_staples": self.variant_staples}


@dataclass(frozen=True)
class Series:
    """A stage's worth of constructs, with the order behind them."""

    stage: str
    purpose: str
    constructs: tuple[Construct, ...]
    core_staples: int
    controls: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def variant_staples(self) -> int:
        return sum(c.variant_staples for c in self.constructs)

    @property
    def total_staples(self) -> int:
        return self.core_staples + self.variant_staples

    #: Modified oligos this series needs, all of them on the shared core.
    modified_oligos: int = 0

    @property
    def modified_cost_eur(self) -> float:
        return round(self.modified_oligos * COST_PER_MODIFIED_OLIGO_EUR, 0)

    @property
    def cost_eur(self) -> float:
        return round(self.total_staples * COST_PER_STAPLE_EUR + self.modified_cost_eur, 0)

    @property
    def cost_without_sharing_eur(self) -> float:
        """What the same series would cost as independent constructs."""
        return round(len(self.constructs) * self.core_staples * COST_PER_STAPLE_EUR, 0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "purpose": self.purpose,
            "constructs": len(self.constructs),
            "core_staples": self.core_staples,
            "variant_staples": self.variant_staples,
            "total_staples": self.total_staples,
            "modified_oligos": self.modified_oligos,
            "modified_oligo_cost_eur": self.modified_cost_eur,
            "estimated_cost_eur": self.cost_eur,
            "cost_if_not_shared_eur": self.cost_without_sharing_eur,
            "saved_by_sharing_eur": round(self.cost_without_sharing_eur - self.cost_eur, 0),
            "controls": list(self.controls),
            "notes": list(self.notes),
        }


def stage0(*, lengths_bp: tuple[int, ...] = (5, 6, 7, 8, 9, 10), gc_variants: int = 4) -> Series:
    """The forward map, one spin: dG_eff(sequence) and the scatter around it.

    The scatter matters more than the map. It is the manufacturing noise floor,
    and it sets the resolution of every stage after this one.
    """
    constructs = [
        Construct(f"L{length}", {"latch_bp": length, "gc": "balanced"}, LATCH_STAPLES)
        for length in lengths_bp
    ]
    constructs += [
        Construct(
            f"GC{fraction}",
            {"latch_bp": 8, "gc_fraction": fraction},
            LATCH_STAPLES,
        )
        for fraction in [round(0.3 + 0.15 * i, 2) for i in range(gc_variants)]
    ]

    return Series(
        stage="0",
        purpose="dG_eff against latch design, and the construct-to-construct scatter",
        constructs=tuple(constructs),
        core_staples=CORE_STAPLES_SINGLE_HINGE,
        modified_oligos=FRET_OLIGOS_ON_CORE,
        controls=(
            "at least 3 independent folds of every construct, to separate folding "
            "variance from synthesis variance",
            "at least 2 independent oligo syntheses for a subset, for the same reason",
            "AFM on each, to confirm the structure folded at all before its dG is believed",
        ),
        notes=(
            f"go/no-go: scatter at fixed design below {STAGE0_SCATTER_GATE_KT} kT. "
            "This is TIGHTER than the source document's ~1 kT, because at 1 kT a "
            "designed 1 kT coupling returns with a median error near 0.85 kT and "
            "Stage 1 cannot then meet its own criterion.",
            "the GC axis is swept at a fixed 8 bp length so length and composition "
            "do not move together and become unattributable",
            "the FRET pair sits across the hinge joint, which is core geometry, so "
            "two modified oligos serve the whole series rather than two per "
            "construct: EUR 300 instead of EUR 3000",
        ),
    )


def stage1(*, bias_levels: tuple[float, ...] = (-2.0, 0.0, 2.0)) -> Series:
    """Two spins: can J and h be tuned independently?

    The decision point of the programme. The measurement is J against applied
    bias, and a horizontal line is success.
    """
    mechanisms = (
        ("mech-short", "mechanical, short strut"),
        ("mech-mid", "mechanical, medium strut"),
        ("mech-long", "mechanical, long strut"),
        ("steric", "steric occlusion"),
        ("strand-short", "strand-mediated, short tether"),
        ("strand-long", "strand-mediated, long tether"),
    )
    # The full grid only on the mechanism most likely to give a clean additive
    # J; corners and centre elsewhere. 9 + 5*5 = 34 would still be too many, so
    # the reduced grid is corners only: 9 + 5*4 = 29, trimmed to the document's
    # "about twenty" by dropping the two strand-mediated variants to corners of
    # a single axis.
    constructs: list[Construct] = []
    primary = mechanisms[1][0]
    for h1, h2 in itertools.product(bias_levels, bias_levels):
        constructs.append(
            Construct(
                f"{primary}_h{h1:+g}_{h2:+g}",
                {"mechanism": primary, "h1": h1, "h2": h2},
                LATCH_STAPLES * 2 + STRUT_STAPLES,
            )
        )
    corners = [(-2.0, -2.0), (-2.0, 2.0), (2.0, -2.0), (2.0, 2.0)]
    for name, _ in mechanisms:
        if name == primary:
            continue
        for h1, h2 in corners[:2] if name.startswith("strand") else corners:
            constructs.append(
                Construct(
                    f"{name}_h{h1:+g}_{h2:+g}",
                    {"mechanism": name, "h1": h1, "h2": h2},
                    LATCH_STAPLES * 2 + STRUT_STAPLES,
                )
            )

    return Series(
        stage="1",
        purpose="measure J, and verify it is constant as h1 and h2 are varied",
        constructs=tuple(constructs),
        core_staples=CORE_STAPLES_TWO_HINGE,
        # Two colour pairs, because Stage 1 needs the joint distribution of two
        # spins and one pair cannot resolve which hinge flipped.
        modified_oligos=2 * FRET_OLIGOS_ON_CORE,
        controls=(
            "an UNCOUPLED pair at every bias setting: two hinges far apart on the "
            "same plate, no strut. Any correlation measured there is an artefact, "
            "and it quantifies the background that |J| has to beat",
            "locked constructs in ALL FOUR joint states (++, +-, -+, --), not in the "
            "two states of one spin. This project's simulation shows a ligation bias "
            "that depends on each spin separately is algebraically a field shift and "
            "CANNOT corrupt J; only a bias depending on the joint state can, and it "
            "adds exactly half itself to the apparent coupling. Calibrating per-site "
            "efficiency is therefore the wrong control",
            "two initial conditions for every measurement -- annealed from high T, and "
            "released from a locked state -- confirming they converge",
        ),
        notes=(
            "go/no-go: |J| above the Stage 0 noise floor by 3 sigma; J constant "
            "across the bias grid to 0.3 kT; uncoupled control below the noise floor",
            "the key plot is fitted J against applied (h1, h2). A slope means the "
            "couplings are bias-dependent and the pairwise Ising form is wrong",
            "a negative result here is publishable and is a real finding about molecular coupling",
        ),
    )


def all_series() -> list[Series]:
    return [stage0(), stage1()]

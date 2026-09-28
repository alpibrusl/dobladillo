"""A bistable hinge: two tiled arms, a single-stranded joint, and a latch.

This is the first part whose prediction is a distribution rather than a shape.
A rectangle either folds or it does not; a hinge is open some fraction of the
time, and that fraction is the thing the whole Hamiltonian programme is built
to design.

Layout. One scaffold rasters across `arm_helices` helices for the full length
of both arms and the joint between them. Staples tile the two arms
independently and never span the joint, so the joint's bases are left as
unpaired scaffold -- one single-stranded tether per helix, which together form
a flexible line the two arms rotate about. Longer joints are floppier; that is
`joint_nt`, and it is a design knob rather than a constant because nothing here
can predict the right value.

The latch is a short duplex between the two arms' outer edges, carried as
unpaired 3' extensions on one pair staple at each end. When the hinge closes,
the two extensions meet and hybridise; the hybridisation free energy is the
bias between the two states, which `sequence.thermo` converts into a field.

Which pair staple can carry the extension is not free. The column parity
alternates along an arm, so a border helix that is part of a pair at one end
of an arm rides on an edge staple at the other; `_lattice.pair_lower` is what answers it,
and a `latch_helix` with no pair at one of the two ends is refused rather than
silently moved.

What this file does not establish. Whether the two extensions can physically
reach each other in the closed state is geometry, and it depends on the joint
length, the arm length and where on the helix the staple's 3' end lands. That
is a question for oxDNA, not for a constructor, and it is the first thing the
simulation pipeline should be pointed at. A latch that cannot reach produces a
perfectly well-formed design whose measured bias is simply the unlatched one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.interfaces import Brick, Port
from dobladillo.parts._lattice import (
    DOMAIN_NT,
    SPAN_MULTIPLE_NT,
    add_raster_scaffold,
    add_twist_correction,
    pair_lower,
    tile_staples,
)
from dobladillo.sequence.thermo import (
    Duplex,
    duplex,
    is_self_complementary,
    latch_field_kt,
    reverse_complement,
)

if TYPE_CHECKING:
    import scadnano as sc

#: Defaults, defined here rather than restated in the CLI.
DEFAULT_ARM_HELICES = 12
DEFAULT_ARM_LENGTH = 192
DEFAULT_LATCH_HELIX = 1

#: Unpaired scaffold bases per helix at the joint. Eight is about 5 nm of
#: single-stranded DNA at 0.63 nm/base, comfortably longer than the ~2 nm it
#: has to span, so the joint is a hinge rather than a hinge under tension. It
#: is not optimised: a shorter joint stiffens the mechanism and a longer one
#: costs conformational entropy on closing, and which trade is right is what
#: Stage 0's intercept measures.
DEFAULT_JOINT_NT = 8

#: A balanced 8 bp latch. Stage 0 sweeps around this.
DEFAULT_LATCH = "GCATGCAT"

#: Column parity each arm starts on, set by where the scaffold turns: arm A
#: starts at the raster's near-end turns and arm B ends at its far-end ones.
#: See `_lattice.tile_staples`. Each arm is its own duplex -- the joint is
#: single-stranded -- so the two are phased independently.
_FIRST_PARITY = {"a": 1, "b": 0}


@dataclass(frozen=True)
class Hinge:
    """A built hinge, its accounting, and the bias it is predicted to have."""

    design: sc.Design
    arm_helices: int
    arm_length: int
    joint_nt: int
    #: None for the locked-open reference: no latch, so never latched.
    latch: Duplex | None
    latch_helix: int
    scaffold: ad.ScaffoldAccounting
    staple_count: int
    staple_lengths: tuple[int, ...]
    #: Further latches, each (duplex, helix), on other helices. They close
    #: together with the first, so their fields add: this is the locked-latched
    #: reference, strong enough to stay shut whatever the conformational cost.
    extra_latches: tuple[tuple[Duplex, int], ...] = ()

    @property
    def total_length(self) -> int:
        return 2 * self.arm_length + self.joint_nt

    @property
    def arm_dimensions_nm(self) -> tuple[float, float]:
        """One arm's footprint, from scadnano's geometry rather than ours."""
        width = float(self.arm_length * ad.GEOMETRY.rise_per_base_pair)
        height = float(self.arm_helices * ad.interhelix_spacing_nm())
        return (width, height)

    def field_kt(self, *, temperature_k: float = 310.15, conformational_kt: float = 0.0) -> float:
        """The predicted Ising field. Sequence only unless the conformational
        cost measured by Stage 0 is supplied; see `sequence.thermo`."""
        if self.latch is None:
            raise ValueError("a locked-open hinge has no latch: p(latched) is 0 by construction")
        # Every latch forms when the hinge closes, so their free energies add;
        # the conformational cost is paid once, with the first.
        return latch_field_kt(
            self.latch, temperature_k=temperature_k, conformational_kt=conformational_kt
        ) + sum(latch_field_kt(d, temperature_k=temperature_k) for d, _ in self.extra_latches)

    def brick(self, *, channel: int = 0) -> Brick:
        """This hinge as a brick, with its latch halves declared as ports.

        The latch was already a port before there was a word for it: two
        complementary extensions, one on each arm, that bind each other and
        nothing else. Declaring it makes that checkable -- a film of several
        hinges on one core needs every latch on a different channel, and
        `interfaces.crosstalk` is what says whether it is.
        """
        if self.latch is None:
            return Brick(name="hinge-locked-open", ports=())
        return Brick(
            name=f"hinge-{self.latch.sequence}",
            ports=(
                Port(
                    name="latch-a",
                    kind="latch",
                    polarity="a",
                    helices=(self.latch_helix,),
                    offset=0,
                    channel=channel,
                ),
                Port(
                    name="latch-b",
                    kind="latch",
                    polarity="b",
                    helices=(self.latch_helix,),
                    offset=self.total_length,
                    channel=channel,
                ),
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        width, height = self.arm_dimensions_nm
        return {
            "part": "hinge",
            "lattice": "square",
            "arm_helices": self.arm_helices,
            "arm_length_bp": self.arm_length,
            "joint_nt": self.joint_nt,
            "latch": None
            if self.latch is None
            else {
                "sequence": self.latch.sequence,
                "length_bp": self.latch.length_bp,
                "gc_fraction": round(self.latch.gc_fraction, 3),
                "dg_kcal_per_mol_37c": round(self.latch.dg_kcal(), 2),
                "helix": self.latch_helix,
            },
            "extra_latches": [
                {"sequence": d.sequence, "length_bp": d.length_bp, "helix": h}
                for d, h in self.extra_latches
            ],
            "predicted_field_kt": None if self.latch is None else round(self.field_kt(), 3),
            "conformational_offset": "not predicted; measured as the intercept of a Stage 0 sweep",
            "scaffold": self.scaffold.as_dict(),
            "staple_count": self.staple_count,
            "staple_length_nt": {
                "min": min(self.staple_lengths),
                "max": max(self.staple_lengths),
                "distinct": sorted(set(self.staple_lengths)),
            },
            "approx_arm_dimensions_nm": {"width": round(width, 1), "height": round(height, 1)},
        }


def _latch_anchor(
    *, arm_length: int, latch_helix: int, arm_helices: int, arm: str
) -> tuple[int, int]:
    """Where a latch extension hangs from, as (lower helix, column offset in its arm).

    Arm A's outer edge is its first column and arm B's is its last, so the two
    sit at opposite column parities and have to be asked for separately.
    """
    if arm == "a":
        column_index, offset = 0, 0
    else:
        column_index = arm_length // DOMAIN_NT - 1
        offset = arm_length - DOMAIN_NT
    lower = pair_lower(
        latch_helix,
        column_index=column_index,
        helices=arm_helices,
        first_parity=_FIRST_PARITY[arm],
    )
    if lower is None:
        raise ValueError(
            f"helix {latch_helix} takes an edge staple rather than a pair staple at the "
            f"outer edge of arm {arm.upper()}, so it cannot carry a latch there; the "
            "column parity alternates, so try an adjacent helix"
        )
    return lower, offset


def bistable_hinge(
    *,
    arm_helices: int = DEFAULT_ARM_HELICES,
    arm_length: int = DEFAULT_ARM_LENGTH,
    joint_nt: int = DEFAULT_JOINT_NT,
    latch_sequence: str | None = DEFAULT_LATCH,
    latch_helix: int = DEFAULT_LATCH_HELIX,
    extra_latches: tuple[tuple[str, int], ...] = (),
    scaffold_variant: str = "p7249",
    scaffold_rotation: int = 5587,
    twist_corrected: bool = True,
) -> Hinge:
    """Build the hinge.

    `arm_length` must be a multiple of 64: an even number of 16-bp columns
    keeps the last column's crossovers off the scaffold's turn, and whole
    64-bp periods let the twist correction be exact.

    `latch_sequence=None` builds the locked-open reference: the same hinge,
    every staple identical, but no latch extensions, so it can never latch.
    FRET needs it (see `hamiltonian.fret_estimate`): a bulk efficiency is a
    population average, and turning it into p(latched) takes the efficiency
    of each pure state, measured on constructs locked in that state.

    `extra_latches`, as (sequence, helix) pairs, adds latches on other helices.
    That is how the locked-LATCHED reference is built without an oligo longer
    than the 60-nt limit. One latch strong enough to stay shut at every offset
    Stage 0 can measure needs 22 bp, and its carrier staple would then be 70 nt.
    """
    if arm_length % SPAN_MULTIPLE_NT:
        raise ValueError(f"arm_length must be a multiple of {SPAN_MULTIPLE_NT}, got {arm_length}")
    if arm_helices % 2:
        raise ValueError(f"arm_helices must be even, got {arm_helices}")
    if joint_nt < 1:
        raise ValueError(f"a joint needs at least one unpaired base, got {joint_nt}")
    if not 0 <= latch_helix < arm_helices:
        raise ValueError(f"latch_helix {latch_helix} is outside 0..{arm_helices - 1}")

    latches: list[tuple[str, int]] = []
    if latch_sequence is not None:
        latches.append((latch_sequence.upper().strip(), latch_helix))
    elif extra_latches:
        raise ValueError("extra latches need a first latch")
    latches += [(seq.upper().strip(), helix) for seq, helix in extra_latches]
    if len({h for _, h in latches}) != len(latches):
        raise ValueError("two latches on one helix would share a carrier staple")
    if len({seq for seq, _ in latches}) != len(latches):
        raise ValueError(
            "latches must differ: identical halves on different helices pair across helices"
        )
    duplexes: list[Duplex] = []
    for seq, helix in latches:
        if not 0 <= helix < arm_helices:
            raise ValueError(f"latch helix {helix} is outside 0..{arm_helices - 1}")
        if is_self_complementary(seq):
            raise ValueError(
                f"latch {seq} is self-complementary: the two arms' extensions "
                "would bind their own copies as readily as each other"
            )
        duplexes.append(duplex(seq))
    latch = duplexes[0] if duplexes else None

    total = 2 * arm_length + joint_nt
    available = ad.scaffold_length(scaffold_variant)
    routed = arm_helices * total
    if routed > available:
        raise ValueError(
            f"{arm_helices} helices of {total} bases need {routed} nt of scaffold, "
            f"but {scaffold_variant} has {available}"
        )

    anchors = [
        (
            _latch_anchor(arm_length=arm_length, latch_helix=h, arm_helices=arm_helices, arm="a"),
            _latch_anchor(arm_length=arm_length, latch_helix=h, arm_helices=arm_helices, arm="b"),
        )
        for _, h in latches
    ]

    design = ad.new_design(helices=arm_helices, max_offset=total, grid="square")
    add_raster_scaffold(design, helices=arm_helices, length=total)

    arm_b_start = arm_length + joint_nt
    tile_staples(
        design,
        helices=arm_helices,
        start=0,
        stop=arm_length,
        extensions={a: len(seq) for (seq, _), (a, _b) in zip(latches, anchors, strict=True)},
        first_parity=_FIRST_PARITY["a"],
    )
    tile_staples(
        design,
        helices=arm_helices,
        start=arm_b_start,
        stop=total,
        extensions={
            (b[0], arm_b_start + b[1]): len(seq)
            for (seq, _), (_a, b) in zip(latches, anchors, strict=True)
        },
        first_parity=_FIRST_PARITY["b"],
    )

    deletions = 0
    if twist_corrected:
        deletions += add_twist_correction(design, helices=arm_helices, start=0, stop=arm_length)
        deletions += add_twist_correction(
            design, helices=arm_helices, start=arm_b_start, stop=total
        )

    ad.assign_scaffold_sequence(design, variant=scaffold_variant, rotation=scaffold_rotation)

    # The latch halves, now that the scaffold has fixed everything it can.
    placed = 0
    for (seq, _), (a, b) in zip(latches, anchors, strict=True):
        placed += ad.assign_extension_sequence(
            design, min_offset=0, max_offset=arm_length, sequence=seq, anchor=a
        )
        placed += ad.assign_extension_sequence(
            design,
            min_offset=arm_b_start,
            max_offset=total,
            sequence=reverse_complement(seq),
            anchor=(b[0], arm_b_start + b[1]),
        )
    if placed != 2 * len(latches):
        raise AssertionError(
            f"expected one extension per latch per arm, placed {placed}; the anchors are "
            "wrong and the design would be ordered without a latch"
        )

    lengths = ad.staple_lengths(design)
    return Hinge(
        design=design,
        arm_helices=arm_helices,
        arm_length=arm_length,
        joint_nt=joint_nt,
        latch=latch,
        latch_helix=latch_helix,
        extra_latches=tuple((d, h) for d, (_, h) in zip(duplexes[1:], latches[1:], strict=True)),
        scaffold=ad.ScaffoldAccounting(
            variant=scaffold_variant,
            total_nt=available,
            routed_nt=ad.scaffold_strand(design).dna_length(),
            deletions=deletions,
        ),
        staple_count=len(lengths),
        staple_lengths=tuple(lengths),
    )

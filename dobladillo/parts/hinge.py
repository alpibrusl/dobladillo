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


#: Depth, in bp, of the band along each arm's joint-side edge. An arm's
#: direction is measured from this band's centroid to the arm's, so it needs
#: no joint position (a long joint's single strands wander) and no fit. One
#: staple column.
EDGE_BP = DOMAIN_NT


@dataclass(frozen=True)
class HingeParticles:
    """Which oxDNA particles are which part of a hinge, read off the design.

    Indices follow `_scadnano.nucleotide_indices` -- strands in design order,
    domains in strand order, 5' to 3', deletions skipped, extensions counted --
    so they address the topology `write_oxdna_files` writes. Arm, joint and
    latch come from each nucleotide's helix offset, never from index ranges:
    the scaffold rasters through both arms and the joint on every helix, so
    no contiguous range is one arm.
    """

    #: Every particle of each arm, its staples' extensions included.
    arm_a: tuple[int, ...]
    arm_b: tuple[int, ...]
    #: The EDGE_BP-deep band of each arm along the joint.
    edge_a: tuple[int, ...]
    edge_b: tuple[int, ...]
    #: The joint's unpaired scaffold, and where along the joint each sits:
    #: 0 at arm A's end, 1 at arm B's.
    joint: tuple[int, ...]
    joint_fraction: tuple[float, ...]
    #: The 3'-terminal paired base of the first latch's carrier staple on each
    #: arm: where the latch hangs from. Present on a locked-open hinge too,
    #: which has the same staples without the extensions.
    anchor_a: int
    anchor_b: int
    #: The first latch's two extensions, 5' to 3'; empty on a locked-open hinge.
    latch_a: tuple[int, ...]
    latch_b: tuple[int, ...]

    @property
    def latch_pairs(self) -> tuple[tuple[int, int], ...]:
        """The designed latch base pairs. The halves are reverse complements
        and pair antiparallel: the first base of one with the last of the other."""
        return tuple(zip(self.latch_a, reversed(self.latch_b), strict=True))

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm_a": len(self.arm_a),
            "arm_b": len(self.arm_b),
            "edge_a": len(self.edge_a),
            "edge_b": len(self.edge_b),
            "joint": len(self.joint),
            "anchor_a": self.anchor_a,
            "anchor_b": self.anchor_b,
            "latch_a": list(self.latch_a),
            "latch_b": list(self.latch_b),
        }


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

    def particles(self) -> HingeParticles:
        """Arm, joint and latch particles, for a trajectory of this design."""
        arm_b_start = self.arm_length + self.joint_nt

        def arm_of(offset: int) -> str | None:
            if offset < self.arm_length:
                return "a"
            return "b" if offset >= arm_b_start else None

        arms: dict[str, list[int]] = {"a": [], "b": []}
        edges: dict[str, list[int]] = {"a": [], "b": []}
        joint: list[int] = []
        fraction: list[float] = []
        extension_of: dict[int, tuple[int, ...]] = {}
        n = 0
        for s, strand in enumerate(self.design.strands):
            bound = [d for d in strand.domains if hasattr(d, "helix")]
            homes = {arm_of(o) for d in bound for o in range(d.start, d.end)} - {None}
            for domain in strand.domains:
                if not hasattr(domain, "helix"):
                    # The same count `nucleotide_indices` advances by.
                    length = len(getattr(domain, "dna_sequence", "") or "")
                    if len(homes) != 1:
                        raise ValueError(f"strand {s} carries an extension but spans both arms")
                    (home,) = homes
                    indices = tuple(range(n, n + length))
                    arms[str(home)] += indices
                    extension_of[s] = indices
                    n += length
                    continue
                offsets = list(range(domain.start, domain.end))
                if not domain.forward:
                    offsets.reverse()
                for offset in offsets:
                    if offset in domain.deletions:
                        continue
                    which = arm_of(offset)
                    if which is None:
                        joint.append(n)
                        fraction.append((offset - self.arm_length + 0.5) / self.joint_nt)
                    else:
                        arms[which].append(n)
                        inner = (
                            offset >= self.arm_length - EDGE_BP
                            if which == "a"
                            else offset < arm_b_start + EDGE_BP
                        )
                        if inner:
                            edges[which].append(n)
                    n += 1

        index = ad.nucleotide_indices(self.design)
        anchors: dict[str, int] = {}
        latches: dict[str, tuple[int, ...]] = {}
        for which, (low, high) in (("a", (0, self.arm_length)), ("b", (arm_b_start, None))):
            helix, column = _latch_anchor(
                arm_length=self.arm_length,
                latch_helix=self.latch_helix,
                arm_helices=self.arm_helices,
                arm=which,
            )
            start = column if which == "a" else arm_b_start + column
            carriers = [
                (s, strand)
                for s, strand in enumerate(self.design.strands)
                if not strand.is_scaffold
                and any(
                    getattr(d, "helix", None) == helix and d.start == start for d in strand.domains
                )
                and all(
                    low <= d.start and (high is None or d.end <= high)
                    for d in strand.domains
                    if hasattr(d, "helix")
                )
            ]
            if len(carriers) != 1:
                raise ValueError(
                    f"expected one latch carrier on arm {which.upper()}, found {len(carriers)}"
                )
            s, strand = carriers[0]
            last = [d for d in strand.domains if hasattr(d, "helix")][-1]
            ends = (
                range(last.end - 1, last.start - 1, -1)
                if last.forward
                else range(last.start, last.end)
            )
            end = next(o for o in ends if o not in last.deletions)
            anchors[which] = index[(last.helix, end, last.forward)]
            latches[which] = extension_of.get(s, ())

        return HingeParticles(
            arm_a=tuple(arms["a"]),
            arm_b=tuple(arms["b"]),
            edge_a=tuple(edges["a"]),
            edge_b=tuple(edges["b"]),
            joint=tuple(joint),
            joint_fraction=tuple(fraction),
            anchor_a=anchors["a"],
            anchor_b=anchors["b"],
            latch_a=latches["a"],
            latch_b=latches["b"],
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

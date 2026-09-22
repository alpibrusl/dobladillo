"""A six-helix bundle on the honeycomb lattice.

The workhorse strut of 3D origami: six helices in a hexagonal ring around a
hollow core, stiff enough that its persistence length is measured in microns
rather than the ~50 nm of a bare duplex.

Ring placement. The six grid positions below form a closed 6-cycle in the
honeycomb neighbour graph, with nothing at its centre. They were found by
asking scadnano to convert grid positions to real coordinates and keeping the
pairs exactly one inter-helix spacing apart, rather than by trusting a
remembered convention for which (h, v) are adjacent.

Why a ring is easier to staple than a rectangle: every helix has exactly two
neighbours and there are no border helices, so the alternating pairing that
tiles the bundle never leaves an uncovered edge, and no single-domain edge
staples are needed.

Periodicity. Honeycomb places crossovers every 7 bp, and 21 bp is exactly two
turns at 10.5 bp/turn, so the lattice is twist-neutral: unlike the square
lattice this needs no corrective deletions. Domains are 21 nt, a multiple of
the crossover spacing, which puts staples at 42 nt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.constants import Lattice

if TYPE_CHECKING:
    import scadnano as sc

#: A closed hexagonal ring in honeycomb grid coordinates, hollow at the centre.
#: Verified as a 6-cycle of nearest neighbours; see tests.
RING_POSITIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 1),
    (2, 1),
    (2, 2),
    (1, 2),
    (0, 2),
)

HELICES = len(RING_POSITIONS)

#: The two staple spans, and the reason they differ.
#:
#: A crossover can only form where the backbone faces its neighbour, so the
#: offset at which one happens IS an angle: 34.29 deg per base, which makes
#: honeycomb's 7 bp spacing 240 deg -- the same as -120, which is the angular
#: separation of neighbours on this lattice.
#:
#: The first version of this file used one span of 21 for both pair families.
#: Spans of equal length tile at multiples of 21, so every crossover in the
#: object landed at phase 0, and each helix bonded BOTH its neighbours at the
#: same azimuth while they sit 120 deg apart. One bond of every pair was made
#: 120 deg off, the same way all around the ring, and the bundle came out of
#: oxDNA as a 269 nm arc. See docs/BUNDLE_BEND.md.
#:
#: Unequal spans fix it. 28 then 14 puts the boundaries at 0, 28, 42, 70, ...
#: which is phase 0, 7, 0, 7 -- so one pair family crosses at phase 7 and the
#: other at 0, differing by the 7 bp the lattice asks for. Both are multiples
#: of the crossover spacing, so every crossover still lands where the lattice
#: allows one.
SPAN_A_NT = 4 * Lattice.HONEYCOMB_CROSSOVER_BP  # 28
SPAN_B_NT = 2 * Lattice.HONEYCOMB_CROSSOVER_BP  # 14

#: One full pairing cycle: both families, once each.
BLOCK_NT = SPAN_A_NT + SPAN_B_NT  # 42

#: The longest domain, for the seed rule. 28 clears the 14 nt requirement.
DOMAIN_NT = SPAN_A_NT

#: Default, defined here rather than restated in the CLI.
DEFAULT_LENGTH = 1176


@dataclass(frozen=True)
class Bundle:
    design: sc.Design
    length: int
    scaffold: ad.ScaffoldAccounting
    staple_count: int
    staple_lengths: tuple[int, ...]

    @property
    def length_nm(self) -> float:
        """Axial length, using scadnano's rise rather than ours. See constants."""
        return float(self.length * ad.GEOMETRY.rise_per_base_pair)

    @property
    def diameter_nm(self) -> float:
        """Across the ring: two helix spacings plus a helix."""
        spacing = 2 * ad.GEOMETRY.helix_radius + ad.GEOMETRY.inter_helix_gap
        return float(2 * spacing + 2 * ad.GEOMETRY.helix_radius)

    def as_dict(self) -> dict[str, Any]:
        return {
            "part": "six_helix_bundle",
            "lattice": "honeycomb",
            "helices": HELICES,
            "length_bp": self.length,
            "scaffold": self.scaffold.as_dict(),
            "staple_count": self.staple_count,
            "staple_length_nt": {
                "min": min(self.staple_lengths),
                "max": max(self.staple_lengths),
                "distinct": sorted(set(self.staple_lengths)),
            },
            "approx_dimensions_nm": {
                "length": round(self.length_nm, 1),
                "diameter": round(self.diameter_nm, 1),
            },
            "twist_corrected": False,
            "twist_correction_note": "honeycomb is twist-neutral; no deletions needed",
        }


def _scaffold_runs_forward(helix: int) -> bool:
    return helix % 2 == 0


def _add_scaffold(design: sc.Design, *, length: int) -> None:
    builder = ad.draw(design, 0, 0).to(length)
    for helix in range(1, HELICES):
        if _scaffold_runs_forward(helix):
            builder = builder.cross(helix, 0).to(length)
        else:
            builder = builder.cross(helix, length).to(0)
    builder.as_scaffold()


def _add_pair_staple(design: sc.Design, *, a: int, b: int, start: int, span: int) -> None:
    """One staple covering `span` bases on helix `a` and the same on `b`.

    The crossover lands at `start + span`, which is what makes the span length
    a phase rather than a mere size.
    """
    stop = start + span
    if _scaffold_runs_forward(a):
        ad.draw(design, b, start).to(stop).cross(a, stop).to(start)
    else:
        ad.draw(design, a, start).to(stop).cross(b, stop).to(start)


def _add_staples(design: sc.Design, *, length: int) -> None:
    """Two pair families per block, on different spans so they cross at
    different phases.

    Family A takes the even pairs (0,1), (2,3), (4,5) for the first 28 bases of
    the block; family B takes the odd pairs (1,2), (3,4), (5,0) for the
    remaining 14. Six is even, so each helix belongs to exactly one pair of
    each family and is covered once, end to end.
    """
    for block_start in range(0, length, BLOCK_NT):
        for k in range(0, HELICES, 2):
            _add_pair_staple(design, a=k, b=(k + 1) % HELICES, start=block_start, span=SPAN_A_NT)
        for k in range(1, HELICES, 2):
            _add_pair_staple(
                design,
                a=k,
                b=(k + 1) % HELICES,
                start=block_start + SPAN_A_NT,
                span=SPAN_B_NT,
            )


def six_helix_bundle(
    *,
    length: int = DEFAULT_LENGTH,
    scaffold_variant: str = "p7249",
    scaffold_rotation: int = 5587,
) -> Bundle:
    """Build the bundle.

    Defaults route 7056 of M13mp18's 7249 bases through six helices; the
    remainder folds as an unpaired loop and is reported.
    """
    if length % BLOCK_NT:
        raise ValueError(f"length must be a multiple of {BLOCK_NT}, got {length}")

    available = ad.scaffold_length(scaffold_variant)
    routed = HELICES * length
    if routed > available:
        raise ValueError(
            f"{HELICES} helices of {length} bases need {routed} nt of scaffold, "
            f"but {scaffold_variant} has {available}"
        )

    design = ad.new_design_at(positions=RING_POSITIONS, max_offset=length, grid="honeycomb")
    _add_scaffold(design, length=length)
    _add_staples(design, length=length)
    ad.assign_scaffold_sequence(design, variant=scaffold_variant, rotation=scaffold_rotation)

    lengths = ad.staple_lengths(design)
    return Bundle(
        design=design,
        length=length,
        scaffold=ad.ScaffoldAccounting(
            variant=scaffold_variant,
            total_nt=available,
            routed_nt=ad.scaffold_strand(design).dna_length(),
            deletions=0,
        ),
        staple_count=len(lengths),
        staple_lengths=tuple(lengths),
    )

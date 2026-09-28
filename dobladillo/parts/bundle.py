"""A six-helix bundle on the honeycomb lattice.

The workhorse strut of 3D origami: six helices in a hexagonal ring around a
hollow core, stiff enough that its persistence length is measured in microns
rather than the ~50 nm of a bare duplex.

**The staple pattern is scadnano's, not ours.** It is the repeating 42-bp unit
of scadnano's example six-helix bundle (MIT;
`tests/data/reference_designs/6_helix_bundle_honeycomb.sc`), on the same ring
ordering. Every staple is 42 nt and crosses two or three times.

Two tilings of our own came first, and both were misphased. Honeycomb allows
each pair of neighbours one crossover phase in the 21-bp repeat, and on a
ring that phase is DIFFERENT for each of the six pairs. The first version used
one 21-nt span for every pair. That put every crossover at one phase and bent
the bundle into a 269 nm arc in oxDNA (docs/BUNDLE_BEND.md). The second split
the pairs into two families with spans of 28 and 14. That gave each FAMILY a
phase, but three pairs need three phases, so two thirds of the crossovers
stayed off: 44 deg rms against 20-22 for published designs. The unit below
scores 17 deg. `routing.azimuth` measured all three.

**The scaffold turns through unpaired bases at the helix ends.** A raster turns
at the same offset on every helix, but each pair needs its own phase, so no
single end offset suits them all. The published design staggers its helix
ends. Here the scaffold instead runs `END_NT` bases past the staples at each
end, and turns in single-stranded DNA, where there is no backbone orientation
to get wrong. `END_NT` also keeps the scaffold's turns clear of the staples'
crossovers at the ends.

Honeycomb is twist-neutral (21 bp is two turns at 10.5 bp/turn), so there are
no deletions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.constants import STAPLE_CROSSOVER_CLEARANCE_BP

if TYPE_CHECKING:
    import scadnano as sc

#: A closed hexagonal ring in honeycomb grid coordinates, hollow at the centre,
#: in the order scadnano's example bundle uses. The staple unit below indexes
#: helices by this order, so the two must change together. Verified as a
#: 6-cycle of nearest neighbours; see tests.
RING_POSITIONS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (0, 1),
    (0, 2),
    (1, 2),
    (2, 2),
    (2, 1),
)

HELICES = len(RING_POSITIONS)

#: One period of the staple pattern: two honeycomb repeats.
BLOCK_NT = 42

#: The staples of one block, 5' to 3', as (helix, start, stop) within the
#: block. Taken from scadnano's example bundle, offsets 42-84. Each helix is
#: covered exactly once and no staple leaves the block, so blocks tile.
UNIT: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((5, 0, 7), (0, 0, 7), (1, 0, 14), (2, 0, 14)),
    ((0, 7, 14), (5, 7, 14), (4, 0, 14), (3, 0, 14)),
    ((3, 14, 28), (2, 14, 28), (1, 14, 28)),
    ((4, 14, 28), (5, 14, 28), (0, 14, 28)),
    ((2, 28, 42), (3, 28, 42), (4, 28, 42)),
    ((1, 28, 42), (0, 28, 42), (5, 28, 42)),
)

#: Unpaired scaffold bases at each end of every helix, where the scaffold turns.
#: The clearance rule sets the floor: a staple crossover sits at the first
#: base of the first block.
END_NT = STAPLE_CROSSOVER_CLEARANCE_BP

#: Default duplex length, defined here rather than restated in the CLI.
DEFAULT_LENGTH = 1176


@dataclass(frozen=True)
class Bundle:
    design: sc.Design
    #: Double-stranded length; each helix also carries END_NT unpaired
    #: scaffold bases at each end.
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
            "unpaired_scaffold_per_helix_end_nt": END_NT,
            "twist_corrected": False,
            "twist_correction_note": "honeycomb is twist-neutral; no deletions needed",
        }


def _scaffold_runs_forward(helix: int) -> bool:
    return helix % 2 == 0


def _add_scaffold(design: sc.Design, *, span: int) -> None:
    builder = ad.draw(design, 0, 0).to(span)
    for helix in range(1, HELICES):
        if _scaffold_runs_forward(helix):
            builder = builder.cross(helix, 0).to(span)
        else:
            builder = builder.cross(helix, span).to(0)
    builder.as_scaffold()


def _add_staples(design: sc.Design, *, start: int, length: int) -> None:
    """Tile `UNIT` over `[start, start + length)`, opposite the scaffold."""
    for block_start in range(start, start + length, BLOCK_NT):
        for staple in UNIT:
            builder = None
            for helix, lo, hi in staple:
                lo, hi = block_start + lo, block_start + hi
                begin, end = (hi, lo) if _scaffold_runs_forward(helix) else (lo, hi)
                if builder is None:
                    builder = ad.draw(design, helix, begin).to(end)
                else:
                    builder = builder.cross(helix, begin).to(end)


def six_helix_bundle(
    *,
    length: int = DEFAULT_LENGTH,
    scaffold_variant: str = "p7249",
    scaffold_rotation: int = 5587,
) -> Bundle:
    """Build the bundle.

    Defaults pair 7056 of M13mp18's 7249 bases in six helices and leave 60 more
    unpaired at the helix ends, where the scaffold turns; the remainder folds
    as an unpaired loop and is reported.
    """
    if length % BLOCK_NT:
        raise ValueError(f"length must be a multiple of {BLOCK_NT}, got {length}")

    available = ad.scaffold_length(scaffold_variant)
    span = length + 2 * END_NT
    routed = HELICES * span
    if routed > available:
        raise ValueError(
            f"{HELICES} helices of {span} bases need {routed} nt of scaffold, "
            f"but {scaffold_variant} has {available}"
        )

    design = ad.new_design_at(positions=RING_POSITIONS, max_offset=span, grid="honeycomb")
    _add_scaffold(design, span=span)
    _add_staples(design, start=END_NT, length=length)
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

"""A Rothemund-style rectangle on the square lattice, twist-corrected.

Layout. The scaffold rasters back and forth across `helices` helices, each
`length` bases long, which is the standard boustrophedon of a 2D origami.

Staples tile that raster in 32 nt pieces, each one 16 nt on one helix and 16 nt
on its neighbour. Two domains rather than three on purpose: the design rules
ask us to avoid the short-long-short "sandwich" pattern, and 16 nt clears the
14 nt seed requirement twice over.

The pairing alternates by block, which is the part worth explaining. Every
interior helix borders two neighbours, so tiling every adjacent pair at the
same offsets would cover each interior helix twice. Instead, block k pairs
(0,1),(2,3),... when k is even and (1,2),(3,4),... when k is odd. Each base is
then covered exactly once, and because the pairing alternates along the length,
the helices are stitched to both neighbours rather than falling apart into
independent two-helix ribbons. The outermost helices are left uncovered on
alternate blocks, and take a single 32 nt edge staple there.

Why the length must be a multiple of 64, not just 32. The scaffold turns at the
far end of the raster, and it turns there for the even-numbered helix pairs
(0,1), (2,3) and so on. If the number of staple blocks is odd, the last block
is an even one, so those same pairs also carry a staple crossover at that exact
offset -- zero clearance from the scaffold turn, against a rule that asks for
five bases. With an even number of blocks the last block belongs to the odd
pairs, whose scaffold turns are at the opposite end, and the collision cannot
happen. This was found by the rule checker on the first version of this file,
not by reasoning ahead.

Twist correction. The square lattice puts crossovers every 8 bp and calls 32 bp
three turns, which implies 10.67 bp/turn against B-DNA's relaxed 10.5, so the
object acquires a right-handed global twist. Deleting one base every 64 fixes
it exactly: 63 bases at 10.5 bp/turn is 6.000 turns, which is what the lattice
demands of a 64-base span. See constants.SQUARE_TWIST_CORRECTION_PERIOD_BP for
the derivation and the caveat about published periods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladilo import _scadnano as ad
from dobladilo.constants import SQUARE_TWIST_CORRECTION_PERIOD_BP

if TYPE_CHECKING:
    import scadnano as sc

#: Bases per staple domain. Above the 14 nt seed, and two of them land the
#: staple at 32 nt, inside the 32-42 target band.
DOMAIN_NT = 16

#: A block is one full pairing cycle: two staples deep on each pair.
BLOCK_NT = 2 * DOMAIN_NT

#: Defaults, defined here rather than restated in the CLI. Stating them twice
#: is how the CLI ended up offering a length the generator had just started
#: rejecting.
DEFAULT_HELICES = 22
DEFAULT_LENGTH = 320


@dataclass(frozen=True)
class Rectangle:
    """A built rectangle and the numbers Q1 asks us to account for."""

    design: sc.Design
    helices: int
    length: int
    scaffold: ad.ScaffoldAccounting
    staple_count: int
    staple_lengths: tuple[int, ...]

    @property
    def dimensions_nm(self) -> tuple[float, float]:
        """Rough footprint, using scadnano's own geometry rather than ours.

        Reported against the library that generated the design, so that a
        comparison with a simulated or measured dimension is not silently
        mixing two different values for the rise per base pair. See
        constants.RISE_PER_BP_NM for why that distinction is live.
        """
        width = float(self.length * ad.GEOMETRY.rise_per_base_pair)
        height = float(self.helices * ad.interhelix_spacing_nm())
        return (width, height)

    def as_dict(self) -> dict[str, Any]:
        width, height = self.dimensions_nm
        return {
            "part": "rectangle",
            "lattice": "square",
            "helices": self.helices,
            "length_bp": self.length,
            "scaffold": self.scaffold.as_dict(),
            "staple_count": self.staple_count,
            "staple_length_nt": {
                "min": min(self.staple_lengths),
                "max": max(self.staple_lengths),
                "distinct": sorted(set(self.staple_lengths)),
            },
            "approx_dimensions_nm": {"width": round(width, 1), "height": round(height, 1)},
        }


def _scaffold_runs_forward(helix: int) -> bool:
    """The raster alternates direction; staples must oppose it."""
    return helix % 2 == 0


def _add_scaffold(design: sc.Design, *, helices: int, length: int) -> None:
    builder = ad.draw(design, 0, 0).to(length)
    for helix in range(1, helices):
        if _scaffold_runs_forward(helix):
            builder = builder.cross(helix, 0).to(length)
        else:
            builder = builder.cross(helix, length).to(0)
    builder.as_scaffold()


def _add_pair_staple(design: sc.Design, *, lower: int, start: int) -> None:
    """One 32 nt staple: 16 nt on `lower`, 16 nt on the helix above it.

    Built to run opposite the scaffold on each helix, which is what makes it
    complementary rather than merely adjacent.
    """
    upper = lower + 1
    stop = start + DOMAIN_NT
    if _scaffold_runs_forward(lower):
        # Scaffold forward on `lower`, so the staple must run backward there.
        ad.draw(design, upper, start).to(stop).cross(lower, stop).to(start)
    else:
        ad.draw(design, lower, start).to(stop).cross(upper, stop).to(start)


def _add_edge_staple(design: sc.Design, *, helix: int, start: int) -> None:
    """A single-domain 32 nt staple where a border helix has no partner."""
    stop = start + BLOCK_NT
    if _scaffold_runs_forward(helix):
        ad.draw(design, helix, stop).to(start)
    else:
        ad.draw(design, helix, start).to(stop)


def _add_staples(design: sc.Design, *, helices: int, length: int) -> None:
    for block_start in range(0, length, BLOCK_NT):
        block_index = block_start // BLOCK_NT
        first_lower = block_index % 2
        paired: set[int] = set()

        for lower in range(first_lower, helices - 1, 2):
            paired.update({lower, lower + 1})
            for offset in (block_start, block_start + DOMAIN_NT):
                _add_pair_staple(design, lower=lower, start=offset)

        for helix in range(helices):
            if helix not in paired:
                _add_edge_staple(design, helix=helix, start=block_start)


def _add_twist_correction(design: sc.Design, *, helices: int, length: int) -> int:
    """Delete one base every 64, away from the crossover positions."""
    offsets = list(
        ad.deletion_offsets(
            start=0,
            stop=length,
            period=SQUARE_TWIST_CORRECTION_PERIOD_BP,
            # Half a domain in: crossovers sit at multiples of 16, and a
            # deletion on top of one is needless strain at a junction.
            phase=DOMAIN_NT // 2,
        )
    )
    for helix in range(helices):
        for offset in offsets:
            design.add_deletion(helix, offset)
    return helices * len(offsets)


def rothemund_rectangle(
    *,
    helices: int = DEFAULT_HELICES,
    length: int = DEFAULT_LENGTH,
    scaffold_variant: str = "p7249",
    scaffold_rotation: int = 5587,
    twist_corrected: bool = True,
) -> Rectangle:
    """Build the rectangle.

    Defaults route 7040 of M13mp18's 7249 bases; the remainder folds as an
    unpaired loop and is reported rather than quietly dropped.

    `length` must be a multiple of 64: of 32 so the staple blocks tile exactly,
    and of 64 so there is an even number of them, which is what keeps a staple
    crossover off the scaffold's turn at the far end. `helices` must be even so
    the alternating pairing has no odd helix left over on every block.
    """
    if length % (2 * BLOCK_NT):
        raise ValueError(
            f"length must be a multiple of {2 * BLOCK_NT}, got {length}; an odd number "
            "of blocks puts a staple crossover on the scaffold turn at the far end"
        )
    if helices % 2:
        raise ValueError(f"helices must be even, got {helices}")

    available = ad.scaffold_length(scaffold_variant)
    routed = helices * length
    if routed > available:
        raise ValueError(
            f"{helices} helices of {length} bases need {routed} nt of scaffold, "
            f"but {scaffold_variant} has {available}"
        )

    design = ad.new_design(helices=helices, max_offset=length, grid="square")
    _add_scaffold(design, helices=helices, length=length)
    _add_staples(design, helices=helices, length=length)
    deletions = (
        _add_twist_correction(design, helices=helices, length=length) if twist_corrected else 0
    )
    ad.assign_scaffold_sequence(design, variant=scaffold_variant, rotation=scaffold_rotation)

    lengths = ad.staple_lengths(design)
    return Rectangle(
        design=design,
        helices=helices,
        length=length,
        scaffold=ad.ScaffoldAccounting(
            variant=scaffold_variant,
            total_nt=available,
            routed_nt=ad.scaffold_strand(design).dna_length(),
            deletions=deletions,
        ),
        staple_count=len(lengths),
        staple_lengths=tuple(lengths),
    )

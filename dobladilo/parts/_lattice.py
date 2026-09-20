"""Square-lattice staple tiling, shared by every flat part.

The rectangle worked this out first and it is not obvious, so it lives here
rather than being copied: the block-parity rule below had a real defect that
the rule checker caught, and a second copy would not have been fixed with it.

Every function takes an explicit `[start, stop)` span so a part can tile more
than one region of the same helices -- which is what a hinge is: two tiled
arms with an untiled joint between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dobladilo import _scadnano as ad
from dobladilo.constants import SQUARE_TWIST_CORRECTION_PERIOD_BP

if TYPE_CHECKING:
    import scadnano as sc

#: Bases per staple domain. Above the 14 nt seed, and two of them land the
#: staple at 32 nt, inside the 32-42 target band.
DOMAIN_NT = 16

#: A block is one full pairing cycle: two staples deep on each pair.
BLOCK_NT = 2 * DOMAIN_NT

#: A tiled span must be a multiple of this: of BLOCK_NT so the blocks tile
#: exactly, and of twice it so there is an even number of them, which is what
#: keeps a staple crossover off the scaffold's turn at the far end.
SPAN_MULTIPLE_NT = 2 * BLOCK_NT


def scaffold_runs_forward(helix: int) -> bool:
    """The raster alternates direction; staples must oppose it."""
    return helix % 2 == 0


def check_span(start: int, stop: int) -> int:
    length = stop - start
    if length <= 0:
        raise ValueError(f"empty span [{start}, {stop})")
    if length % SPAN_MULTIPLE_NT:
        raise ValueError(
            f"span must be a multiple of {SPAN_MULTIPLE_NT}, got {length}; an odd "
            "number of blocks puts a staple crossover on the scaffold turn at the far end"
        )
    return length


def add_raster_scaffold(design: sc.Design, *, helices: int, length: int) -> None:
    """The boustrophedon: across, up, back, up, across again."""
    builder = ad.draw(design, 0, 0).to(length)
    for helix in range(1, helices):
        if scaffold_runs_forward(helix):
            builder = builder.cross(helix, 0).to(length)
        else:
            builder = builder.cross(helix, length).to(0)
    builder.as_scaffold()


def pair_lower(helix: int, *, block_index: int, helices: int) -> int | None:
    """Which pair staple covers `helix` in this block, by its lower helix.

    None when the helix is unpaired in that block and takes an edge staple
    instead -- which happens to helix 0 on odd blocks, and to the top helix on
    whichever parity leaves it over. A caller that wants to hang something off
    a pair staple has to ask, because the parity alternates and the answer is
    different at the two ends of an arm.
    """
    parity = block_index % 2
    if helix < parity:
        return None
    lower = parity + 2 * ((helix - parity) // 2)
    if lower + 1 > helices - 1:
        return None
    return lower


def add_pair_staple(
    design: sc.Design,
    *,
    lower: int,
    start: int,
    extension_nt: int = 0,
) -> None:
    """One 32 nt staple: 16 nt on `lower`, 16 nt on the helix above it.

    Built to run opposite the scaffold on each helix, which is what makes it
    complementary rather than merely adjacent.

    An extension, when asked for, hangs off the 3' end as unpaired bases. That
    is how a latch is attached: it binds nothing on this object and everything
    on the other arm. Its sequence is NOT set here -- see
    `_scadnano.assign_extension_sequence` for why it cannot be.
    """
    upper = lower + 1
    stop = start + DOMAIN_NT
    if scaffold_runs_forward(lower):
        # Scaffold forward on `lower`, so the staple must run backward there.
        builder = ad.draw(design, upper, start).to(stop).cross(lower, stop).to(start)
    else:
        builder = ad.draw(design, lower, start).to(stop).cross(upper, stop).to(start)
    if extension_nt:
        builder.extension_3p(extension_nt)


def add_edge_staple(design: sc.Design, *, helix: int, start: int) -> None:
    """A single-domain 32 nt staple where a border helix has no partner."""
    stop = start + BLOCK_NT
    if scaffold_runs_forward(helix):
        ad.draw(design, helix, stop).to(start)
    else:
        ad.draw(design, helix, start).to(stop)


def tile_staples(
    design: sc.Design,
    *,
    helices: int,
    start: int,
    stop: int,
    extension_at: tuple[int, int] | None = None,
    extension_nt: int = 0,
) -> None:
    """Tile `[start, stop)` across `helices`.

    The pairing alternates by block. Every interior helix borders two
    neighbours, so tiling every adjacent pair at the same offsets would cover
    each interior helix twice. Instead block k pairs (0,1),(2,3),... when k is
    even and (1,2),(3,4),... when k is odd. Each base is then covered exactly
    once, and because the pairing alternates along the length the helices are
    stitched to both neighbours rather than falling apart into independent
    two-helix ribbons. The outermost helices are left uncovered on alternate
    blocks and take a single 32 nt edge staple there.

    `extension_at` is a (lower helix, block start offset) naming the one pair
    staple that carries an extension.
    """
    check_span(start, stop)
    for block_start in range(start, stop, BLOCK_NT):
        block_index = (block_start - start) // BLOCK_NT
        first_lower = block_index % 2
        paired: set[int] = set()

        for lower in range(first_lower, helices - 1, 2):
            paired.update({lower, lower + 1})
            for offset in (block_start, block_start + DOMAIN_NT):
                carries = extension_at == (lower, offset)
                add_pair_staple(
                    design, lower=lower, start=offset, extension_nt=extension_nt if carries else 0
                )

        for helix in range(helices):
            if helix not in paired:
                add_edge_staple(design, helix=helix, start=block_start)


def add_twist_correction(design: sc.Design, *, helices: int, start: int, stop: int) -> int:
    """Delete one base every 64, away from the crossover positions.

    The square lattice puts crossovers every 8 bp and calls 32 bp three turns,
    which implies 10.67 bp/turn against B-DNA's relaxed 10.5, so the object
    acquires a right-handed global twist. Deleting one base every 64 fixes it
    exactly: 63 bases at 10.5 bp/turn is 6.000 turns, which is what the lattice
    demands of a 64-base span. See constants.SQUARE_TWIST_CORRECTION_PERIOD_BP
    for the derivation and the caveat about published periods.

    The phase is measured from `start`, so each tiled region is corrected on
    its own lattice rather than on a global one it may not share.
    """
    offsets = list(
        ad.deletion_offsets(
            start=start,
            stop=stop,
            period=SQUARE_TWIST_CORRECTION_PERIOD_BP,
            # Half a domain in: crossovers sit at multiples of 16, and a
            # deletion on top of one is needless strain at a junction.
            phase=(start + DOMAIN_NT // 2) % SQUARE_TWIST_CORRECTION_PERIOD_BP,
        )
    )
    for helix in range(helices):
        for offset in offsets:
            design.add_deletion(helix, offset)
    return helices * len(offsets)

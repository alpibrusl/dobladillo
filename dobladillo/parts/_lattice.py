"""Square-lattice staple tiling for parts scadnano's rectangle cannot build.

The rectangle and twist pair are built by scadnano's `origami_rectangle`. The
hinge cannot be: one scaffold runs through two arms and an unpaired joint
whose length is a free knob, not a multiple of scadnano's 16-bp column. So the
hinge is tiled here, on the same pattern.

**The pattern, and the defect it replaces.** A staple crossover can only be
made where the backbone faces the partner helix. On the square lattice the
two in-plane neighbours of a helix sit on opposite sides, and 16 bp is a turn
and a half, so crossovers every 16 bp must ALTERNATE partner: (0,1),(2,3),...
at one column boundary, (1,2),(3,4),... at the next. That is Rothemund's
pattern. The first version of this file alternated every 32 bp instead, which
gave each helix two crossovers to the same partner 16 bp apart, one of them on
the wrong face. Half of every crossover in every square part was strained by
~180 deg; `routing.azimuth` found it, calibrated on published designs.

Here each column is tiled with 32-nt U-staples, 16 nt on each helix of a
pair, crossing at the column's right boundary; the pairing parity is the
column's. The two border helices are unpaired in odd columns. Their cell is
joined to the neighbouring pair staple in the SAME column through a crossover
at the column's left boundary. That boundary has the opposite parity, which is
exactly the partner the border helix needs there. So edge staples are 48 nt,
16+16+16, and no crossover breaks the alternation.

Every function takes an explicit `[start, stop)` span, so a part can tile more
than one region of the same helices. A hinge is two tiled arms with an
untiled joint between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dobladillo import _scadnano as ad
from dobladillo.constants import SQUARE_TWIST_CORRECTION_PERIOD_BP

if TYPE_CHECKING:
    import scadnano as sc

#: Bases per staple domain, and the width of one column: the distance between
#: consecutive crossovers on a helix, which alternate between its neighbours.
DOMAIN_NT = 16

#: A tiled span must be a multiple of this. Of 32, so there is an even number
#: of columns: the last column then pairs (1,2),(3,4),..., and its crossovers
#: stay off the scaffold's turn, which pairs (0,1),(2,3),... at the far end.
#: Of 64, so the twist correction deletes one base per whole period.
SPAN_MULTIPLE_NT = SQUARE_TWIST_CORRECTION_PERIOD_BP


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


def pair_lower(helix: int, *, column_index: int, helices: int, first_parity: int = 0) -> int | None:
    """Which pair staple covers `helix` in this column, by its lower helix.

    None when the helix is a border helix left unpaired in that column, whose
    cell rides on the neighbouring pair staple instead -- helix 0 and the top
    helix, on odd columns. A caller that wants to hang something off a pair
    staple has to ask, because the parity alternates and the answer is
    different at the two ends of an arm.
    """
    parity = (column_index + first_parity) % 2
    if helix < parity:
        return None
    lower = parity + 2 * ((helix - parity) // 2)
    if lower + 1 > helices - 1:
        return None
    return lower


def _cell(
    builder: sc.StrandBuilder | None, design: sc.Design, helix: int, start: int
) -> sc.StrandBuilder:
    """Continue a staple across one 16-bp cell of `helix`, opposite the scaffold.

    A staple enters a cell at one end and leaves at the other, so the offset
    it starts drawing from is set by its direction on that helix.
    """
    stop = start + DOMAIN_NT
    forward = not scaffold_runs_forward(helix)
    begin, end = (start, stop) if forward else (stop, start)
    if builder is None:
        return ad.draw(design, helix, begin).to(end)
    return builder.cross(helix, begin).to(end)


def add_column_staple(
    design: sc.Design,
    *,
    lower: int,
    start: int,
    helices: int,
    extension_nt: int = 0,
) -> None:
    """The staple for pair (`lower`, `lower`+1) in the column at `start`.

    32 nt, crossing at the column's right boundary. If the pair borders an
    unpaired border helix, that helix's cell is joined on through the left
    boundary, making 48 nt.

    The staple is drawn 5' to 3'. On an even-lower pair it starts on the upper
    helix, which puts its one crossover at the right boundary. On an odd-lower
    pair it starts on the lower helix, or on helix 0 when that is joined on,
    and walking upward alternates left and right boundaries by construction.
    """
    upper = lower + 1
    if lower % 2 == 0:
        chain = [upper, lower]
    else:
        chain = [lower, upper]
        if lower == 1:
            chain.insert(0, 0)  # helix 0 is unpaired in this column
        if upper == helices - 2:
            chain.append(helices - 1)  # so is the top helix
    builder = None
    for helix in chain:
        builder = _cell(builder, design, helix, start)
    if extension_nt and builder is not None:
        builder.extension_3p(extension_nt)


def tile_staples(
    design: sc.Design,
    *,
    helices: int,
    start: int,
    stop: int,
    extension_at: tuple[int, int] | None = None,
    extension_nt: int = 0,
    first_parity: int = 0,
    extensions: dict[tuple[int, int], int] | None = None,
) -> None:
    """Tile `[start, stop)` across `helices`, one column at a time.

    Column c pairs (0,1),(2,3),... when c + `first_parity` is even and
    (1,2),(3,4),... when it is odd, so the partner of every helix alternates
    at each 16-bp boundary.

    `first_parity` is set by the scaffold, not chosen. The scaffold's
    crossovers sit a minor groove (150 deg) round from the staples', so where
    the scaffold turns at the end of a span, the staple pattern must pair the
    OTHER parity at that boundary. That is also how scadnano's rectangle is
    laid out. The raster turns pair (1,2),(3,4),... at offset 0 and
    (0,1),(2,3),... at the far end. So a span that starts at a scaffold turn
    takes `first_parity=1`, and one that ends at a far-end turn takes 0.
    Getting it wrong puts every scaffold turn on the wrong face, about 140 deg.

    `extension_at` is a (lower helix, column start offset) naming the one pair
    staple that carries an extension; `extensions` maps several such anchors
    to their lengths, for a part with more than one.
    """
    check_span(start, stop)
    if helices < 4 or helices % 2:
        raise ValueError(f"tiling needs an even number of helices, at least 4; got {helices}")
    for column_start in range(start, stop, DOMAIN_NT):
        parity = ((column_start - start) // DOMAIN_NT + first_parity) % 2
        for lower in range(parity, helices - 1, 2):
            wanted = dict(extensions or {})
            if extension_at is not None:
                wanted[extension_at] = extension_nt
            add_column_staple(
                design,
                lower=lower,
                start=column_start,
                helices=helices,
                extension_nt=wanted.get((lower, column_start), 0),
            )


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

"""A Rothemund-style rectangle on the square lattice, twist-corrected.

Built by scadnano's `origami_rectangle.create` (MIT), not by a tiling of our
own. The first version here tiled staples in 32-bp blocks and put two
crossovers to the SAME neighbour 16 bp apart -- a turn and a half, so half of
every staple's crossovers sat on the far side of the helix from their partner.
Scored against published designs with `routing.azimuth`, it was randomly
phased (89 deg rms phasing strain, against 18-22 for every reference). Nothing
else in the toolchain had noticed, and oligos were one purchase away.

The pattern scadnano implements is Rothemund's (Nature 2006): staple
crossovers on every 16-bp column boundary, with the partner ALTERNATING from
one boundary to the next -- (0,1),(2,3),... on even boundaries, (1,2),(3,4),...
on odd ones. At the lattice's 10.67 bp/turn, 16 bp is a turn and a half, so
consecutive crossovers face opposite sides of the helix, which is exactly
where the two neighbours are. Most staples are 8+16+8 across three helices;
the rule checker reports those as `sandwich` warnings, and they are the
published design, not a defect.

What stays ours: the scaffold (M13mp18 p7249 at a chosen rotation), the
accounting, the brick interface, and where the twist-correcting deletions go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.constants import SQUARE_TWIST_CORRECTION_PERIOD_BP
from dobladillo.interfaces import Brick, Port

if TYPE_CHECKING:
    import scadnano as sc

__all__ = [
    "COLUMN_NT",
    "DEFAULT_HELICES",
    "DEFAULT_LENGTH",
    "Rectangle",
    "rothemund_rectangle",
]

#: One column of the Rothemund pattern: the distance between consecutive
#: staple crossovers on a helix, which alternate between its two neighbours.
COLUMN_NT = 16

#: Where in its column a twist-correcting deletion goes: the middle, as far as
#: possible from the crossovers on both column boundaries.
_DELETION_IN_COLUMN = COLUMN_NT // 2

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

    def brick(self, *, channel: int = 0) -> Brick:
        """This rectangle as a brick, with its two ends declared as edges.

        The ends rather than the sides: the scaffold runs along the helices, so
        joining two slabs end to end is a different operation from stacking
        them, and only the first is an `edge`. Stacking is what E7's
        multi-layer plate needs and is not offered here yet.
        """
        helices = tuple(range(self.helices))
        return Brick(
            name=f"rectangle-{self.helices}x{self.length}",
            ports=(
                Port(
                    name="start",
                    kind="edge",
                    polarity="a",
                    helices=helices,
                    offset=0,
                    channel=channel,
                ),
                Port(
                    name="end",
                    kind="edge",
                    polarity="b",
                    helices=helices,
                    offset=self.length,
                    channel=channel,
                ),
            ),
        )

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


def rothemund_rectangle(
    *,
    helices: int = DEFAULT_HELICES,
    length: int = DEFAULT_LENGTH,
    scaffold_variant: str = "p7249",
    scaffold_rotation: int = 5587,
    twist_corrected: bool = True,
) -> Rectangle:
    """Build the rectangle.

    Defaults route 6930 of M13mp18's 7249 bases after 110 deletions; the
    remainder folds as an unpaired loop and is reported rather than quietly
    dropped.

    `length` must be a multiple of 64, the twist-correction period: one base is
    deleted per 64 on every helix, and a partial period would leave the last
    stretch under-corrected. `helices` must be even so the scaffold raster
    ends on the side it started.
    """
    if length % SQUARE_TWIST_CORRECTION_PERIOD_BP:
        raise ValueError(
            f"length must be a multiple of {SQUARE_TWIST_CORRECTION_PERIOD_BP}, got {length}; "
            "the twist correction deletes one base per period, and a partial period "
            "leaves the last stretch under-corrected"
        )
    if helices % 2:
        raise ValueError(f"helices must be even, got {helices}")
    if length < 2 * SQUARE_TWIST_CORRECTION_PERIOD_BP:
        # Measured: at four columns scadnano's generator draws an edge staple
        # past the end of the helix and refuses its own design.
        raise ValueError(
            f"length must be at least {2 * SQUARE_TWIST_CORRECTION_PERIOD_BP}, got {length}; "
            "scadnano's rectangle generator cannot tile four columns"
        )

    available = ad.scaffold_length(scaffold_variant)
    routed = helices * length
    if routed > available:
        raise ValueError(
            f"{helices} helices of {length} bases need {routed} nt of scaffold, "
            f"but {scaffold_variant} has {available}"
        )

    from scadnano import origami_rectangle

    design = origami_rectangle.create(
        num_helices=helices,
        num_cols=length // COLUMN_NT,
        assign_seq=False,
        num_flanking_columns=0,
        # Spacing is in columns: 4 x 16 = 64 bp, our derived period (see
        # constants). scadnano's own default elsewhere is 3 columns, 48 bp;
        # both score as well phased, and 64 is the one derived here.
        twist_correction_deletion_spacing=(
            SQUARE_TWIST_CORRECTION_PERIOD_BP // COLUMN_NT if twist_corrected else 0
        ),
        twist_correction_deletion_offset=_DELETION_IN_COLUMN,
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
            # The scaffold's, not the design's: scadnano marks each deletion on
            # the staple domain too, and a base pair deleted is one deletion.
            deletions=sum(len(d.deletions) for d in ad.scaffold_strand(design).domains),
        ),
        staple_count=len(lengths),
        staple_lengths=tuple(lengths),
    )

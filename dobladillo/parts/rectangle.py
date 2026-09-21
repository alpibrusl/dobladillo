"""A Rothemund-style rectangle on the square lattice, twist-corrected.

Layout. The scaffold rasters back and forth across `helices` helices, each
`length` bases long, which is the standard boustrophedon of a 2D origami.

Staples tile that raster in 32 nt pieces, each one 16 nt on one helix and 16 nt
on its neighbour. Two domains rather than three on purpose: the design rules
ask us to avoid the short-long-short "sandwich" pattern, and 16 nt clears the
14 nt seed requirement twice over.

The tiling itself, the block-parity rule, the reason a span must be a multiple
of 64 and the twist correction all live in `parts._lattice`, because the hinge
needs the same lattice over two spans instead of one. What is left here is the
rectangle: a single span, a continuous raster, and the scaffold accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dobladillo import _scadnano as ad
from dobladillo.parts._lattice import (
    BLOCK_NT,
    DOMAIN_NT,
    SPAN_MULTIPLE_NT,
    add_raster_scaffold,
    add_twist_correction,
    tile_staples,
)

if TYPE_CHECKING:
    import scadnano as sc

__all__ = [
    "BLOCK_NT",
    "DOMAIN_NT",
    "DEFAULT_HELICES",
    "DEFAULT_LENGTH",
    "Rectangle",
    "rothemund_rectangle",
]

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
    if length % SPAN_MULTIPLE_NT:
        raise ValueError(
            f"length must be a multiple of {SPAN_MULTIPLE_NT}, got {length}; an odd "
            "number of blocks puts a staple crossover on the scaffold turn at the far end"
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
    add_raster_scaffold(design, helices=helices, length=length)
    tile_staples(design, helices=helices, start=0, stop=length)
    deletions = (
        add_twist_correction(design, helices=helices, start=0, stop=length)
        if twist_corrected
        else 0
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

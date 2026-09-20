"""A height map, and nothing about DNA.

The unit this module works in. An AFM produces a grid of heights with a known
physical pixel size; everything downstream -- flattening, segmentation,
measurement -- needs only that. Keeping the type this plain is what lets the
module be handed to a lab that has no interest in the rest of this project,
and lets it be tested on images whose contents we chose.

Instrument file readers convert into this. They are the only part that needs
to know about Bruker, JPK or Nanosurf.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class HeightMap:
    """Heights in nanometres, on a square grid of known pitch."""

    heights_nm: np.ndarray
    pixel_nm: float
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.heights_nm.ndim != 2:
            raise ValueError(f"expected a 2D image, got {self.heights_nm.ndim} dimensions")
        if self.pixel_nm <= 0:
            raise ValueError(f"pixel size must be positive, got {self.pixel_nm}")

    @property
    def shape(self) -> tuple[int, int]:
        rows, cols = self.heights_nm.shape
        return rows, cols

    @property
    def size_nm(self) -> tuple[float, float]:
        rows, cols = self.shape
        return rows * self.pixel_nm, cols * self.pixel_nm

    def with_heights(self, heights_nm: np.ndarray) -> HeightMap:
        return HeightMap(heights_nm=heights_nm, pixel_nm=self.pixel_nm, source=self.source)

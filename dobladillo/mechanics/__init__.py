"""Indentation mechanics of our own plates, via `alpibrupa/nanoindent`.

Nothing in here computes contact mechanics. That stack -- Hertz, the
Dimitriadis and Garcia bottom-effect corrections, Chadwick's thin-layer
asymptotic, and an axisymmetric finite-element solver -- already exists and is
validated in `nanoindent`. This module supplies the piece nanoindent cannot
know: the thickness of the plate a given design folds into, and hence which of
those models applies to it.
"""

from dobladillo.mechanics.plate import (
    MEASURED_FACTORS,
    NANOINDENT_NOTE,
    Correction,
    Plate,
    Tip,
    correction,
    regime,
    thickness_ladder,
    thin_film_parameter,
)

__all__ = [
    "MEASURED_FACTORS",
    "NANOINDENT_NOTE",
    "Correction",
    "Plate",
    "Tip",
    "correction",
    "regime",
    "thickness_ladder",
    "thin_film_parameter",
]

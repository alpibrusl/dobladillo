"""Unit conversions. The ONLY place a unit is converted.

oxDNA reports lengths in its own simulation unit. Converting ad hoc at each
call site is how a factor of 0.85 ends up applied twice in one pipeline and
once in another, and the disagreement then looks like physics. Everything
goes through here.
"""

from __future__ import annotations

from typing import TypeVar

import numpy as np

# oxDNA length unit. Snodin et al., J. Chem. Phys. 142, 234901 (2015).
OXDNA_LENGTH_UNIT_NM = 0.8518

#: Conversions apply to a single number or to a whole array of positions, and
#: return the same kind they were given. Typing it as float only was a lie that
#: numpy's broadcasting hid: every trajectory frame is converted as an array.
Length = TypeVar("Length", float, np.ndarray)


def oxdna_to_nm(value: Length) -> Length:
    """oxDNA simulation length units -> nanometres."""
    return value * OXDNA_LENGTH_UNIT_NM


def nm_to_oxdna(value: Length) -> Length:
    """Nanometres -> oxDNA simulation length units."""
    return value / OXDNA_LENGTH_UNIT_NM

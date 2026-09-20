"""Unit conversions. The ONLY place a unit is converted.

oxDNA reports lengths in its own simulation unit. Converting ad hoc at each
call site is how a factor of 0.85 ends up applied twice in one pipeline and
once in another, and the disagreement then looks like physics. Everything
goes through here.
"""

from __future__ import annotations

# oxDNA length unit. Snodin et al., J. Chem. Phys. 142, 234901 (2015).
OXDNA_LENGTH_UNIT_NM = 0.8518


def oxdna_to_nm(value: float) -> float:
    """oxDNA simulation length units -> nanometres."""
    return value * OXDNA_LENGTH_UNIT_NM


def nm_to_oxdna(value: float) -> float:
    """Nanometres -> oxDNA simulation length units."""
    return value / OXDNA_LENGTH_UNIT_NM

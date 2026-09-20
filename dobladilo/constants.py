"""Physical constants and design-rule thresholds, with their sources.

Every number the code relies on lives here with a citation, so a value can be
argued with against its source instead of being found inline three modules
deep. DESIGN.md section 3 is the prose version of this file; if the two ever
disagree, one of them is a bug.

Rules are thresholds, not opinions: the validators in `routing/` read them
from here so that relaxing a rule is a visible, reviewable edit.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------- geometry

#: Rise per base pair in B-DNA, nm.
RISE_PER_BP_NM: Final = 0.34

#: Helical repeat of relaxed B-DNA, bp per turn.
HELICAL_REPEAT_BP: Final = 10.5

#: Bare helix diameter, nm.
HELIX_DIAMETER_NM: Final = 2.0

#: Effective inter-helix spacing in a folded origami, nm. Larger than the bare
#: diameter because of electrostatic repulsion; depends on Mg2+.
INTERHELIX_SPACING_NM: Final = (2.25, 2.6)

#: Persistence length of dsDNA, nm.
PERSISTENCE_LENGTH_DSDNA_NM: Final = 50.0

#: Persistence length of a 6-helix bundle, nm. Bundles are far stiffer than a
#: single duplex, which is why they are the workhorse strut.
PERSISTENCE_LENGTH_6HB_NM: Final = (1000.0, 3000.0)


class Lattice:
    """Crossover periodicity per lattice, and what it does to global twist.

    Honeycomb is twist-neutral because 21 bp is exactly 2 turns at the relaxed
    10.5 bp/turn. Square is not: 32 bp over 3 turns implies 10.67 bp/turn, so
    the helices are over-wound and the object acquires a right-handed global
    twist unless periodic deletions correct it. This is the single most common
    way a square-lattice design comes out visibly wrong.
    """

    HONEYCOMB_CROSSOVER_BP: Final = 7  # to each of 3 neighbours
    HONEYCOMB_PERIOD_BP: Final = 21  # = 2 turns at 10.5 bp/turn
    SQUARE_CROSSOVER_BP: Final = 8
    SQUARE_PERIOD_BP: Final = 32  # = 3 turns, implies 10.67 bp/turn


#: Effective helical repeat imposed by the square lattice's crossover period.
SQUARE_LATTICE_EFFECTIVE_REPEAT_BP: Final = Lattice.SQUARE_PERIOD_BP / 3.0

# --------------------------------------------------------------- scaffolds

#: Scaffold lengths in nt. Sequences live in dobladilo/data/scaffolds/.
SCAFFOLD_LENGTHS_NT: Final = {
    "M13mp18": 7249,
    "p7560": 7560,
    "p8064": 8064,
}

# ------------------------------------------------------------- staple rules
# Hard constraints unless a design explicitly flags an exception. DESIGN.md s3.

#: Allowed staple length, nt.
STAPLE_LENGTH_NT: Final = (20, 60)

#: Preferred staple length, nt. Outside this but inside STAPLE_LENGTH_NT is a
#: warning, not a violation.
STAPLE_LENGTH_TARGET_NT: Final = (32, 42)

#: Every staple needs at least one continuous binding domain this long, which
#: is what nucleates it onto the scaffold.
STAPLE_SEED_DOMAIN_NT: Final = 14

#: A binding domain shorter than this does not hold at folding temperature.
STAPLE_MIN_DOMAIN_NT: Final = 5

#: A staple crossover this close to a scaffold crossover on the same helix
#: pair strains the junction.
STAPLE_CROSSOVER_CLEARANCE_BP: Final = 5

#: Poly-G runs at least this long are flagged: they form G-quadruplexes and
#: synthesise badly.
POLY_G_RUN_FLAG: Final = 4

# ------------------------------------------------------------- wet-lab defaults
# Starting points for protocol sheets, not discoveries. Every one of these is
# screened per design, and the value actually used is recorded with the result.

#: Folding buffer, mM, at pH 8.
BUFFER_TRIS_MM: Final = 5.0
BUFFER_EDTA_MM: Final = 1.0
BUFFER_PH: Final = 8.0

#: Mg2+ screen: origami folding is sharply Mg-dependent, so this is a range to
#: scan rather than a value to assume.
MGCL2_SCREEN_MM: Final = (5.0, 20.0)
MGCL2_SCREEN_STEP_MM: Final = 2.0

#: Scaffold concentration, nM, and staple excess over scaffold.
SCAFFOLD_CONC_NM: Final = (10.0, 20.0)
STAPLE_EXCESS: Final = (5.0, 10.0)

#: Anneal: hold, then a slow ramp. 3D objects need the slow one; 2D tolerates
#: 1 C/min.
ANNEAL_HOLD_C: Final = 65.0
ANNEAL_HOLD_MIN: Final = 15.0
ANNEAL_RAMP_FROM_C: Final = 60.0
ANNEAL_RAMP_TO_C: Final = 40.0
ANNEAL_RAMP_3D_C_PER_H: Final = 1.0
ANNEAL_RAMP_2D_C_PER_MIN: Final = 1.0

# ------------------------------------------------------------ simulation caveats

#: oxDNA2 models monovalent salt only. Mg2+ is not explicit; the convention is
#: to simulate at high [Na+] as a proxy, in M. This MUST be recorded in every
#: result's metadata, because a prediction made at one proxy salt is not
#: comparable to one made at another.
OXDNA_NA_PROXY_M: Final = (0.5, 1.0)

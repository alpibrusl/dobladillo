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
#:
#: scadnano's own Geometry uses 0.332. Both are defensible B-DNA values, but
#: they differ by 2.4%, which propagates straight into any predicted dimension.
#: The rule is: anything compared against a scadnano- or oxDNA-derived number
#: uses THEIR value, read from the library at run time (see `_scadnano.GEOMETRY`
#: and `Rectangle.dimensions_nm`); this constant is the literature figure the
#: design document quotes. A test pins the gap so that a change on either side
#: is noticed rather than absorbed.
RISE_PER_BP_NM: Final = 0.34

#: The rise per base pair as a RANGE, nm: the two B-DNA values this
#: repository already carries, scadnano's Geometry default (0.332, what its
#: drawings and oxDNA exports use; pinned against the library in
#: tests/test_calibration_lateral.py) and RISE_PER_BP_NM above (DESIGN.md s3,
#: Table 1). Used where a length along the helix is a REFERENCE rather than a
#: prediction -- `parts.calibration_tile`, which takes RISE_PER_BP_NM as the
#: nominal and the width of this range as its uncertainty. It is the spread
#: between two defensible values, not a measured variation of origami on
#: mica; see `calibration.lateral` for what that leaves out.
RISE_PER_BP_RANGE_NM: Final = (0.332, RISE_PER_BP_NM)

#: Helical repeat of relaxed B-DNA, bp per turn.
HELICAL_REPEAT_BP: Final = 10.5

#: Bare helix diameter, nm.
HELIX_DIAMETER_NM: Final = 2.0

#: Contour length per base of single-stranded DNA, nm. Used to ask whether two
#: unpaired extensions can physically reach each other; it is the *maximum*
#: span of an ssDNA segment, so a reach computed from it is generous by
#: construction. A real coil is far shorter than its contour length, and the
#: entropy of stretching one out is exactly what the latch's binding energy
#: has to pay for. Treat a "within reach" verdict as necessary, not
#: sufficient.
SSDNA_RISE_PER_BASE_NM: Final = 0.63

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

#: Delete one base every this many, to cancel the square lattice's overwinding.
#:
#: Derivation. The lattice calls a 64-base span 6 turns (32 bp = 3 turns). Left
#: alone, 64 bases of relaxed B-DNA want 64/10.5 = 6.095 turns, and that excess
#: is the global right-handed twist. Remove one base and 63/10.5 = 6.000 turns
#: exactly, which is what the lattice demands. 64 is the shortest period where
#: a whole-base deletion lands exactly; 32 would overshoot (31/10.5 = 2.952
#: against 3).
#:
#: Caveat, flagged rather than resolved: published square-lattice designs also
#: use a 48-base period, which does NOT cancel exactly (47/10.5 = 4.476 against
#: the lattice's 4.5). Whether the residual matters is an empirical question
#: this project is meant to answer, not assume.
SQUARE_TWIST_CORRECTION_PERIOD_BP: Final = 64

# --------------------------------------------------------------- scaffolds

#: Scaffold lengths in nt. Sequences live in dobladillo/data/scaffolds/.
#: Cross-checked against scadnano's own M13 variants at test time.
SCAFFOLD_LENGTHS_NT: Final = {
    "p7249": 7249,  # M13mp18
    "p7560": 7560,
    "p8064": 8064,
    "p8634": 8634,
}

# ------------------------------------------------------------- staple rules
# DESIGN.md s3 set these as hard constraints. On 2026-09-28 the benchmark
# (#14) showed three of them rejecting published designs that fold: the
# Nature 2009 monolith and square nut (Douglas et al., Nature 459, 414) and
# Dietz et al. 2009's 120-deg bundle (Science 325, 725), all in
# tests/data/. Per AGENTS.md rule 8 that was flagged, and the maintainer
# decided to relax each rule to the published evidence. So a HARD limit is
# now one no published, folded design in tests/data crosses; the older
# thresholds survive as preferences, which warn.

#: Allowed staple length, nt. The square nut has 31 staples of 17-19 nt, so
#: the old floor of 20 rejected a published design; 16 keeps a margin under
#: its shortest. The ceiling, 60, is unchanged: nothing published exceeds 49.
STAPLE_LENGTH_NT: Final = (16, 60)

#: Preferred staple length, nt. Outside this but inside STAPLE_LENGTH_NT is a
#: warning, not a violation.
STAPLE_LENGTH_TARGET_NT: Final = (32, 42)

#: A continuous binding domain this long nucleates a staple onto the
#: scaffold, and a staple with one is preferred. A PREFERENCE, not a limit: 97
#: of the monolith's 144 staples have no domain over 7 nt, which is the normal
#: honeycomb pattern of 7-nt segments between crossovers, and it folds.
STAPLE_SEED_DOMAIN_NT: Final = 14

#: A binding domain shorter than this is unlikely to hold at folding
#: temperature, and is warned about.
STAPLE_MIN_DOMAIN_NT: Final = 5

#: A domain shorter than this is refused. The square nut carries 60 domains of
#: 2 nt and folds, so the floor sits at 2; a 1-nt domain binds nothing.
STAPLE_MIN_DOMAIN_HARD_NT: Final = 2

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

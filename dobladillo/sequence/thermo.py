"""Nearest-neighbour duplex thermodynamics, and the latch bias it predicts.

The latch of a hinge is a short duplex. Its hybridisation free energy is what
sets the bias between the two states, so a design that varies latch length and
GC content is varying a field in the Ising sense, and this module is the map
from one to the other.

The parameters are SantaLucia's 1998 unified set, which is a published table of
numbers rather than anyone's code. They are stated at 1 M Na+; everything that
moves away from that -- lower monovalent salt, and in our case Mg2+ rather than
Na+ at all -- is a correction, and the corrections are where the honesty has to
live. See `SALT_NOTE`.

What this module does NOT predict, and the distinction matters for reading
Stage 0: closing a hinge costs conformational entropy that has nothing to do
with the latch sequence. The measurable bias is

    h = -(dG_latch + dG_conformational) / (2 kT)

and only the first term is computed here. The second is geometry, is identical
across constructs that share a staple core, and is therefore exactly what the
*intercept* of a Stage 0 latch sweep measures. Stage 0 is usually described as
a reproducibility test; it is also the only measurement of that offset, and
without it no predicted bias can be converted into an expected p(up).

References
----------
SantaLucia, J. (1998). A unified view of polymer, dumbbell, and oligonucleotide
DNA nearest-neighbor thermodynamics. PNAS 95, 1460-1465.

SantaLucia, J., and D. Hicks (2004). The thermodynamics of DNA structural
motifs. Annu. Rev. Biophys. Biomol. Struct. 33, 415-440.

Owczarzy, R., et al. (2008). Predicting stability of DNA duplexes in solutions
containing magnesium and monovalent cations. Biochemistry 47, 5336-5353.

von Ahsen, N., C. T. Wittwer, and E. Schutz (2001). Oligonucleotide melting
temperatures under PCR conditions. Clin. Chem. 47, 1956-1961.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

#: Gas constant, kcal/(mol K).
R_KCAL: Final = 1.987_204_258_640_83e-3

#: Reference temperature for a quoted dG37, K.
T37_K: Final = 310.15

COMPLEMENT: Final = {"A": "T", "T": "A", "G": "C", "C": "G"}

#: Unified nearest-neighbour parameters, SantaLucia 1998 table 1: enthalpy in
#: kcal/mol and entropy in cal/(mol K), for each 5'->3' dimer paired with its
#: complement, at 1 M NaCl.
NEAREST_NEIGHBOUR: Final[dict[str, tuple[float, float]]] = {
    "AA": (-7.9, -22.2),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7),
    "GT": (-8.4, -22.4),
    "CT": (-7.8, -21.0),
    "GA": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9),
}

#: Helix initiation, by which base pair terminates the duplex. Both ends are
#: counted, so a duplex with one G-C end and one A-T end takes one of each.
INITIATION: Final[dict[str, tuple[float, float]]] = {
    "GC": (0.1, -2.8),
    "AT": (2.3, 4.1),
}

#: Entropy added per phosphate by the monovalent salt correction,
#: cal/(mol K) per ln(M). SantaLucia 1998 eq. 7.
SALT_ENTROPY_PER_PHOSPHATE: Final = 0.368

SALT_NOTE: Final = """\
Our folding buffer is magnesium, not sodium, and the nearest-neighbour table is
stated at 1 M Na+. The conversion used here is the monovalent-equivalent rule
of von Ahsen 2001, Na_eq(mM) = Na(mM) + 120*sqrt(Mg(mM)), which is a PCR rule
of thumb: it was fitted for primer annealing, not for a constrained duplex
held between two origami arms, and Owczarzy 2008 shows the equivalence is not
uniform across sequence composition.

Treat a predicted dG as a design ordering, not a calibrated value. Stage 0
sweeps Mg2+ precisely because this correction cannot be trusted at the 0.3 kT
resolution the programme needs; the sweep measures it rather than assuming it.
"""


def _is_dna(sequence: str) -> bool:
    return bool(sequence) and set(sequence) <= set(COMPLEMENT)


def reverse_complement(sequence: str) -> str:
    return "".join(COMPLEMENT[b] for b in reversed(sequence))


def is_self_complementary(sequence: str) -> bool:
    """A sequence that pairs with itself. As a latch this is a defect -- it
    dimerises with its own copies instead of latching -- and it also breaks the
    melting formula below, so it is worth naming rather than inferring."""
    return sequence.upper() == reverse_complement(sequence.upper())


def gc_fraction(sequence: str) -> float:
    if not _is_dna(sequence):
        raise ValueError(f"not a DNA sequence: {sequence!r}")
    return sum(b in "GC" for b in sequence) / len(sequence)


def sodium_equivalent_m(*, sodium_m: float = 0.0, magnesium_m: float = 0.0) -> float:
    """Monovalent equivalent of a mixed buffer, M. See `SALT_NOTE`."""
    if sodium_m < 0 or magnesium_m < 0:
        raise ValueError("concentrations cannot be negative")
    return sodium_m + 0.120 * math.sqrt(magnesium_m * 1000.0)


@dataclass(frozen=True)
class Duplex:
    """A hybridised sequence and the three numbers that describe it."""

    sequence: str
    dh_kcal: float
    ds_cal: float
    sodium_equivalent_m: float

    @property
    def length_bp(self) -> int:
        return len(self.sequence)

    @property
    def gc_fraction(self) -> float:
        return gc_fraction(self.sequence)

    def dg_kcal(self, temperature_k: float = T37_K) -> float:
        """Hybridisation free energy at a temperature. Negative favours the
        duplex, which is the usual convention and the opposite of the field."""
        return self.dh_kcal - temperature_k * self.ds_cal / 1000.0

    def dg_kt(self, temperature_k: float = T37_K) -> float:
        """The same, in units of kT at that temperature -- what the Ising
        model speaks. A duplex worth 1 kT is worth 0.616 kcal/mol at 37 C and
        0.592 at 25 C, so the unit conversion is not a constant and quoting
        kcal/mol without a temperature is how the two get confused."""
        return self.dg_kcal(temperature_k) / (R_KCAL * temperature_k)

    def melting_k(self, *, strand_m: float = 1e-6) -> float:
        """Tm for two non-self-complementary strands at equal concentration.

        Refuses a self-complementary sequence rather than returning a number
        for it. That case needs the symmetry correction (-1.4 cal/(mol K)) and
        CT rather than CT/4, and applying neither is a silent few-degree error
        -- which is how it was found here, by disagreeing with primer3 on
        exactly the self-complementary members of a test set and on no others.
        It is also a latch nobody should order.
        """
        if is_self_complementary(self.sequence):
            raise ValueError(
                f"{self.sequence} is self-complementary: this melting formula does not "
                "apply to it, and it would dimerise with itself rather than latch"
            )
        return self.dh_kcal * 1000.0 / (self.ds_cal + R_KCAL * 1000.0 * math.log(strand_m / 4.0))

    def melting_c(self, *, strand_m: float = 1e-6) -> float:
        return self.melting_k(strand_m=strand_m) - 273.15


def duplex(sequence: str, *, sodium_m: float = 1.0, magnesium_m: float = 0.0) -> Duplex:
    """Nearest-neighbour thermodynamics of `sequence` against its complement.

    Defaults to the 1 M Na+ reference conditions the table is stated at, so
    that calling this with no buffer reproduces published values rather than
    quietly applying a correction.
    """
    sequence = sequence.upper().strip()
    if not _is_dna(sequence):
        raise ValueError(f"not a DNA sequence: {sequence!r}")
    if len(sequence) < 2:
        raise ValueError("a duplex needs at least two base pairs")

    dh = 0.0
    ds = 0.0
    for i in range(len(sequence) - 1):
        dimer = sequence[i : i + 2]
        if dimer in NEAREST_NEIGHBOUR:
            step = NEAREST_NEIGHBOUR[dimer]
        else:
            # The table lists one of each complementary pair; the other reads
            # the same duplex from the opposite strand.
            step = NEAREST_NEIGHBOUR[reverse_complement(dimer)]
        dh += step[0]
        ds += step[1]

    for end in (sequence[0], sequence[-1]):
        init = INITIATION["GC" if end in "GC" else "AT"]
        dh += init[0]
        ds += init[1]

    na_eq = sodium_equivalent_m(sodium_m=sodium_m, magnesium_m=magnesium_m)
    if na_eq <= 0:
        raise ValueError("a duplex needs some counterion; salt equivalent is zero")
    # Phosphates, not base pairs: a duplex of N bp carries 2(N-1) of them, and
    # SantaLucia's correction is per phosphate on a per-strand basis, so the
    # (N-1) here is the per-strand count.
    ds += SALT_ENTROPY_PER_PHOSPHATE * (len(sequence) - 1) * math.log(na_eq)

    return Duplex(sequence=sequence, dh_kcal=dh, ds_cal=ds, sodium_equivalent_m=na_eq)


def latch_field_kt(
    latch: Duplex,
    *,
    temperature_k: float = T37_K,
    conformational_kt: float = 0.0,
) -> float:
    """The Ising field a latch imposes, in kT.

    Under this project's convention p(s) is proportional to exp(sum h_i s_i +
    ...), with s = +1 the latched state. Latching is favoured when dG is
    negative, so

        h = -(dG_latch + dG_conformational) / (2 kT)

    The factor of two is the one that is easy to lose: p(+)/p(-) = exp(2h), not
    exp(h), because flipping a spin changes h*s by 2h.

    `conformational_kt` defaults to zero, which is not a claim that it is zero.
    It is the offset Stage 0 measures, and leaving it at zero means the
    returned field is the sequence contribution alone.
    """
    return -(latch.dg_kt(temperature_k) + conformational_kt) / 2.0

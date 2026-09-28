"""Nearest-neighbour duplex thermodynamics, and the latch bias it predicts.

The latch of a hinge is a short duplex. Its hybridisation free energy is what
sets the bias between the two states, so a design that varies latch length and
GC content is varying a field in the Ising sense, and this module is the map
from one to the other.

The parameters are SantaLucia's 1998 unified set, stated at 1 M Na+; everything
that moves away from that -- lower monovalent salt, and in our case Mg2+ rather
than Na+ at all -- is a correction, and the corrections are where the honesty
has to live. See `SALT_NOTE`.

Where the numbers come from: primer3, not us
--------------------------------------------
Enthalpy and entropy are computed by primer3's thermodynamic alignment (`thal`,
through primer3-py), which carries the same SantaLucia table and the same salt
correction. This module used to transcribe the table itself. It was right, but
it was a reimplementation of a commodity, and the one bug it did have -- a
melting temperature silently wrong on self-complementary sequences -- was
caught only by disagreeing with primer3. docs/VISION.md s3 draws the
conclusion: replace the commodity, keep only what nobody else does. What is
ours is what sits on top: the salt caveat, the kT conversion, the refusal of
self-complementary latches, and `latch_field_kt`.

primer3-py is therefore a CORE dependency, not an optional extra, and there is
no hand-written fallback table. The two alternatives were considered and
rejected:

* A fallback table used when primer3 is absent is a second source of truth,
  and the environment that runs it is by construction the one where nothing
  checks it. That is not hypothetical: CI installed only the `dev` extra, so
  the primer3 cross-check the old table relied on was skipped on every CI run.
* Keeping primer3 optional "because it is GPL" conflated copyleft with
  incompatible. GPL-2.0-or-later is on EUPL-1.2's compatibility list, and
  tests/test_licences.py records the review.

The cost is real and stated: primer3-py is a C extension, and it publishes
wheels for x86-64 only, so an arm64 install (Apple Silicon, aarch64 Linux)
compiles it and needs a C compiler. The independent reference did not go
away either -- the published table now lives in tests/test_thermo.py as
reference data, and primer3 reached through this adapter has to reproduce it.
That is what catches the mistakes an adapter makes: mM against M, cal against
kcal, the monovalent and divalent arguments swapped.

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

Untergasser, A., et al. (2012). Primer3 -- new capabilities and interfaces.
Nucleic Acids Res. 40, e115. (`thal`, the thermodynamic alignment used here.)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from primer3.thermoanalysis import ThermoAnalysis

#: Gas constant, kcal/(mol K).
R_KCAL: Final = 1.987_204_258_640_83e-3

#: Reference temperature for a quoted dG37, K.
T37_K: Final = 310.15

COMPLEMENT: Final = {"A": "T", "T": "A", "G": "C", "C": "G"}

#: Longest duplex primer3's `thal` will align (THAL_MAX_ALIGN in thal.h): the
#: length up to which a two-state model -- intact duplex or two free strands --
#: is reasonable. Past it, a ThermoAnalysis call does not raise by itself; it
#: returns zeros with `structure_found` still True and the error parked in a
#: message field. Hence `duplex` refuses the length up front AND checks the
#: result. A latch is a dozen bases; nothing here comes near it.
PRIMER3_MAX_LENGTH: Final = 60

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
    """Monovalent equivalent of a mixed buffer, M. See `SALT_NOTE`.

    primer3 applies this same rule internally (`saltCorrectS` in its thal.c,
    in mM); it is restated here so a `Duplex` records the equivalent it was
    computed at, and so the tests can hold primer3 to it."""
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
        duplex, which is the usual convention and the opposite of the field.
        Two-state, temperature-independent H and S: primer3 computes its own
        dG the same way, so this agrees with it at whatever temperature it is
        asked."""
        return self.dh_kcal - temperature_k * self.ds_cal / 1000.0

    def dg_kt(self, temperature_k: float = T37_K) -> float:
        """The same, in units of kT at that temperature -- what the Ising
        model speaks. A duplex worth 1 kT is worth 0.616 kcal/mol at 37 C and
        0.592 at 25 C, so the unit conversion is not a constant and quoting
        kcal/mol without a temperature is how the two get confused."""
        return self.dg_kcal(temperature_k) / (R_KCAL * temperature_k)

    def melting_k(self, *, strand_m: float = 1e-6) -> float:
        """Tm for two non-self-complementary strands at equal concentration.

        The two-state formula over primer3's H and S, not a table of ours. It
        stays here because it takes the strand concentration as an argument,
        and it is held to primer3's own Tm by the tests.

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
    """Nearest-neighbour thermodynamics of `sequence` against its complement,
    computed by primer3.

    Defaults to the 1 M Na+ reference conditions the table is stated at, so
    that calling this with no buffer reproduces published values rather than
    quietly applying a correction.

    The buffer goes to primer3 as it is -- monovalent and divalent separately,
    in the mM primer3 expects -- and primer3 applies the salt correction
    itself: the von Ahsen equivalent of `SALT_NOTE` and SantaLucia's 0.368 per
    nearest-neighbour step, the same rule `sodium_equivalent_m` states, which
    the tests hold the two to. dNTPs are zero: a folding buffer has none, and
    primer3 would otherwise subtract them from the magnesium.

    Only enthalpy and entropy are kept. primer3's dG is at the one temperature
    it was asked for, and it is H - T*S from those same two numbers, so
    `Duplex.dg_kcal` reproduces it at any temperature without a second call.
    Strand concentration does not enter H or S; it moves only the melting
    point, which `Duplex.melting_k` takes as its own argument.
    """
    sequence = sequence.upper().strip()
    # primer3 validates nothing: it scores U, N or lower-case input as if it
    # were something and returns a confident number. So this is checked here.
    if not _is_dna(sequence):
        raise ValueError(f"not a DNA sequence: {sequence!r}")
    if len(sequence) < 2:
        raise ValueError("a duplex needs at least two base pairs")
    if len(sequence) > PRIMER3_MAX_LENGTH:
        raise ValueError(
            f"{len(sequence)} bp is past primer3's {PRIMER3_MAX_LENGTH} bp two-state limit; "
            "a duplex that long does not melt as one unit"
        )

    na_eq = sodium_equivalent_m(sodium_m=sodium_m, magnesium_m=magnesium_m)
    if na_eq <= 0:
        raise ValueError("a duplex needs some counterion; salt equivalent is zero")

    # A fresh ThermoAnalysis per call, rather than primer3's module-level
    # `calc_heterodimer`: that one keeps its buffer in a shared global and
    # resets it on every call, which is state nobody here should have to
    # reason about. Construction costs about two microseconds.
    analysis = ThermoAnalysis(
        mv_conc=sodium_m * 1000.0,
        dv_conc=magnesium_m * 1000.0,
        dntp_conc=0.0,
        dna_conc=1000.0,
        temp_c=T37_K - 273.15,
    )
    result = analysis.calc_heterodimer(sequence, reverse_complement(sequence)).check_exc()
    if not result.structure_found:
        raise ValueError(f"primer3 found no duplex for {sequence} against its complement")
    return Duplex(
        sequence=sequence,
        dh_kcal=float(result.dh) / 1000.0,
        ds_cal=float(result.ds),
        sodium_equivalent_m=na_eq,
    )


@dataclass(frozen=True)
class Structure:
    """One secondary structure primer3 found: a hairpin, or a dimer of two strands.

    `tm_c` is primer3's two-state melting temperature at the strand
    concentration it was asked about (a hairpin's does not depend on it);
    `dg_kcal` is at `temperature_c`. `found` False means primer3 found no
    structure at all, which for an off-target check is the good answer.
    """

    kind: str
    tm_c: float
    dg_kcal: float
    found: bool
    temperature_c: float
    magnesium_m: float
    strand_m: float

    def as_dict(self) -> dict[str, float | str | bool]:
        return {
            "kind": self.kind,
            "tm_c": round(self.tm_c, 1),
            "dg_kcal_per_mol": round(self.dg_kcal, 2),
            "at_c": self.temperature_c,
            "mgcl2_mm": round(self.magnesium_m * 1000.0, 2),
            "strand_nm": round(self.strand_m * 1e9, 1),
            "found": self.found,
        }


def secondary_structure(
    sequence: str,
    partner: str | None = None,
    *,
    kind: str,
    magnesium_m: float,
    sodium_m: float = 0.0,
    strand_m: float = 50e-9,
    temperature_c: float = 25.0,
) -> Structure:
    """primer3's hairpin, homodimer or heterodimer of `sequence`, in a Mg buffer.

    `kind` is "hairpin", "homodimer" or "heterodimer" (which needs `partner`).
    The same buffer handling as `duplex`: monovalent and divalent passed
    separately, in the mM primer3 expects, no dNTPs. For a heterodimer only
    ONE of the two may be longer than primer3's alignment limit -- that is how
    a 22 nt probe is checked against a whole 7,249 nt scaffold in one call.
    """
    sequence = sequence.upper().strip()
    if not _is_dna(sequence):
        raise ValueError(f"not a DNA sequence: {sequence!r}")
    if partner is not None:
        partner = partner.upper().strip()
        if not _is_dna(partner):
            raise ValueError(f"not a DNA sequence: {partner!r}")
    shortest = min(len(sequence), len(partner) if partner else len(sequence))
    if shortest > PRIMER3_MAX_LENGTH:
        raise ValueError(
            f"primer3 aligns at most {PRIMER3_MAX_LENGTH} nt on one side; got {shortest}"
        )
    analysis = ThermoAnalysis(
        mv_conc=sodium_m * 1000.0,
        dv_conc=magnesium_m * 1000.0,
        dntp_conc=0.0,
        dna_conc=strand_m * 1e9,
        temp_c=temperature_c,
    )
    if kind == "hairpin":
        result = analysis.calc_hairpin(sequence)
    elif kind == "homodimer":
        result = analysis.calc_homodimer(sequence)
    elif kind == "heterodimer":
        if partner is None:
            raise ValueError("a heterodimer needs a partner sequence")
        result = analysis.calc_heterodimer(sequence, partner)
    else:
        raise ValueError(f"kind is hairpin, homodimer or heterodimer, got {kind!r}")
    result.check_exc()
    return Structure(
        kind=kind,
        tm_c=float(result.tm),
        dg_kcal=float(result.dg) / 1000.0,
        found=bool(result.structure_found),
        temperature_c=temperature_c,
        magnesium_m=magnesium_m,
        strand_m=strand_m,
    )


@dataclass(frozen=True)
class Hybrid:
    """The most stable structure primer3 finds between two strands, or within one.

    Unlike `Duplex`, the two strands are arbitrary: this is what answers "does
    this sticky end bind something it should not", where the partner is a
    staple, a stretch of scaffold, or another sticky end, and the structure is
    whatever partial match thal's alignment finds. `melting_c` is primer3's,
    at the strand concentration the hybrid was computed for; a hairpin's does
    not depend on concentration.
    """

    kind: str  # "heterodimer" | "hairpin"
    first: str
    second: str
    found: bool
    dg_kcal: float
    melting_c: float
    temperature_c: float
    strand_m: float

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "first": self.first,
            "second": self.second,
            "found": self.found,
            "dg_kcal": round(self.dg_kcal, 2),
            "melting_c": round(self.melting_c, 1),
            "at_c": self.temperature_c,
            "strand_nm": round(self.strand_m * 1e9, 3),
        }


#: What `Hybrid.melting_c` reads when primer3 finds no structure at all:
#: absolute zero, so "no structure" compares as colder than any threshold.
NO_STRUCTURE_C: Final = -273.15


def _analysis(*, sodium_m: float, magnesium_m: float, temperature_c: float, strand_m: float) -> Any:
    if sodium_equivalent_m(sodium_m=sodium_m, magnesium_m=magnesium_m) <= 0:
        raise ValueError("a hybrid needs some counterion; salt equivalent is zero")
    if strand_m <= 0:
        raise ValueError(f"strand concentration must be positive, got {strand_m}")
    return ThermoAnalysis(
        mv_conc=sodium_m * 1000.0,
        dv_conc=magnesium_m * 1000.0,
        dntp_conc=0.0,
        dna_conc=strand_m * 1e9,  # primer3 takes nM
        temp_c=temperature_c,
    )


def _checked(sequence: str) -> str:
    sequence = sequence.upper().strip()
    if not _is_dna(sequence):
        raise ValueError(f"not a DNA sequence: {sequence!r}")
    if len(sequence) > PRIMER3_MAX_LENGTH:
        raise ValueError(
            f"{len(sequence)} nt is past primer3's {PRIMER3_MAX_LENGTH}-nt alignment limit; "
            "split it into overlapping windows"
        )
    return sequence


def hybrid(
    first: str,
    second: str,
    *,
    sodium_m: float = 0.0,
    magnesium_m: float,
    temperature_c: float,
    strand_m: float,
) -> Hybrid:
    """The strongest heterodimer between two arbitrary strands, by primer3.

    Magnesium has no default on purpose: this answers questions about a
    specific buffer, and a default would quietly answer them about another.
    Both strands are refused past primer3's 60-nt limit, where thal returns a
    confident zero rather than an error.
    """
    a, b = _checked(first), _checked(second)
    analysis = _analysis(
        sodium_m=sodium_m, magnesium_m=magnesium_m, temperature_c=temperature_c, strand_m=strand_m
    )
    result = analysis.calc_heterodimer(a, b).check_exc()
    found = bool(result.structure_found)
    return Hybrid(
        kind="heterodimer",
        first=a,
        second=b,
        found=found,
        dg_kcal=float(result.dg) / 1000.0 if found else 0.0,
        melting_c=float(result.tm) if found else NO_STRUCTURE_C,
        temperature_c=temperature_c,
        strand_m=strand_m,
    )


def hairpin(
    sequence: str,
    *,
    sodium_m: float = 0.0,
    magnesium_m: float,
    temperature_c: float,
) -> Hybrid:
    """The strongest hairpin a single strand forms, by primer3."""
    s = _checked(sequence)
    analysis = _analysis(
        sodium_m=sodium_m, magnesium_m=magnesium_m, temperature_c=temperature_c, strand_m=1e-6
    )
    result = analysis.calc_hairpin(s).check_exc()
    found = bool(result.structure_found)
    return Hybrid(
        kind="hairpin",
        first=s,
        second=s,
        found=found,
        dg_kcal=float(result.dg) / 1000.0 if found else 0.0,
        melting_c=float(result.tm) if found else NO_STRUCTURE_C,
        temperature_c=temperature_c,
        strand_m=0.0,
    )


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

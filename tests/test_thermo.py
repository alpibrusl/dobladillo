"""Nearest-neighbour thermodynamics: primer3, held to the published table.

`sequence.thermo` computes duplex enthalpy and entropy through primer3 and no
longer carries a table of its own. The table did not disappear; it moved here,
as reference data. primer3 is someone else's code and our adapter is the part
that can be wrong -- mM against M, cal against kcal, magnesium passed as
sodium -- and every one of those mistakes shows up as a disagreement with the
paper. So these are conformance tests: the dependency, reached through our
adapter, must reproduce SantaLucia 1998 on every latch the ladder can choose.

These tests used to skip without the optional `thermo` extra, and CI never
installed it, so the cross-check never ran there. primer3 is a core
dependency now and nothing here skips.
"""

from __future__ import annotations

import math

import primer3 as _p3
import pytest

from dobladillo.hamiltonian.bracket import (
    DESIGN_MAGNESIUM_M,
    DESIGN_TEMPERATURE_K,
    candidate_latches,
)
from dobladillo.hamiltonian.model import Ising, distribution
from dobladillo.sequence.thermo import (
    NO_STRUCTURE_C,
    PRIMER3_MAX_LENGTH,
    R_KCAL,
    T37_K,
    duplex,
    gc_fraction,
    hairpin,
    hybrid,
    is_self_complementary,
    latch_field_kt,
    reverse_complement,
    sodium_equivalent_m,
)

#: Deliberately none of them self-complementary; that case is tested apart.
CASES = ("CGTTGA", "AGTCGTAC", "GGCATTACCG", "ACGGTCATTGCA", "TTTTTTTT", "GCGGCGGC")

#: Unified nearest-neighbour parameters, SantaLucia 1998 table 1: enthalpy in
#: kcal/mol and entropy in cal/(mol K), for each 5'->3' dimer paired with its
#: complement, at 1 M NaCl. Reference data, transcribed from the paper.
SANTALUCIA_1998: dict[str, tuple[float, float]] = {
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

#: Helix initiation by terminal pair, SantaLucia 1998. Both ends count.
INITIATION_1998: dict[str, tuple[float, float]] = {"GC": (0.1, -2.8), "AT": (2.3, 4.1)}

#: Salt correction, cal/(mol K) per nearest-neighbour step per ln(M); eq. 7.
SALT_ENTROPY_PER_STEP = 0.368

#: How far primer3 is allowed to sit from the 1998 table. It is not zero, and
#: why is known: primer3 carries the SantaLucia & Hicks 2004 initiation
#: (dS = -5.7 e.u. for the duplex plus a terminal A-T penalty) where 1998
#: splits it by end (-2.8 per G-C end, so -5.6). Every duplex therefore
#: differs by a constant 0.1 cal/(mol K), which is 0.03 kcal/mol, 0.025 kT of
#: field at 25 C, and it shifts every latch alike. Anything larger is a real
#: disagreement.
DS_TOLERANCE_CAL = 0.2
DH_TOLERANCE_KCAL = 0.05
DG_TOLERANCE_KCAL = 0.05


def _published(sequence: str, *, na_eq_m: float = 1.0) -> tuple[float, float]:
    """dH (kcal/mol) and dS (cal/(mol K)) summed straight from the paper."""
    dh = ds = 0.0
    for i in range(len(sequence) - 1):
        dimer = sequence[i : i + 2]
        step = SANTALUCIA_1998.get(dimer) or SANTALUCIA_1998[reverse_complement(dimer)]
        dh += step[0]
        ds += step[1]
    for end in (sequence[0], sequence[-1]):
        init = INITIATION_1998["GC" if end in "GC" else "AT"]
        dh += init[0]
        ds += init[1]
    ds += SALT_ENTROPY_PER_STEP * (len(sequence) - 1) * math.log(na_eq_m)
    return dh, ds


def test_reverse_complement_is_an_involution() -> None:
    for s in CASES:
        assert reverse_complement(reverse_complement(s)) == s


def test_the_reference_table_covers_every_dimer() -> None:
    """Ten entries cover sixteen dimers, because each stands for itself and
    its reverse complement. If one were missing, the reference would raise a
    KeyError on some ordinary sequence rather than on an obvious one."""
    bases = "ACGT"
    for a in bases:
        for b in bases:
            dimer = a + b
            assert dimer in SANTALUCIA_1998 or reverse_complement(dimer) in SANTALUCIA_1998


def test_gc_content_raises_free_energy_magnitude() -> None:
    at = duplex("ATATATAT" + "AA")
    gc = duplex("GCGGCGGC" + "GG")
    assert gc.dg_kcal() < at.dg_kcal()


def test_longer_latches_bind_harder() -> None:
    values = [duplex("GCATGCATGCAT"[:n]).dg_kcal() for n in range(4, 13)]
    assert values == sorted(values, reverse=True)


def test_kt_and_kcal_agree_at_the_stated_temperature() -> None:
    d = duplex("GGCATTACCG")
    assert d.dg_kt(T37_K) == pytest.approx(d.dg_kcal(T37_K) / (R_KCAL * T37_K))


def test_a_kt_is_not_a_fixed_number_of_kcal() -> None:
    """The unit conversion carries a temperature. Quoting kcal/mol without one
    is how a 4% error gets into a bias."""
    d = duplex("GGCATTACCG")
    assert d.dg_kt(T37_K) != pytest.approx(d.dg_kt(298.15), rel=1e-3)


def test_magnesium_is_converted_to_a_monovalent_equivalent() -> None:
    assert sodium_equivalent_m(magnesium_m=0.012) == pytest.approx(0.120 * math.sqrt(12.0))
    assert sodium_equivalent_m(sodium_m=0.05, magnesium_m=0.0) == 0.05


def test_lower_salt_destabilises() -> None:
    strong = duplex("GGCATTACCG", sodium_m=1.0)
    weak = duplex("GGCATTACCG", sodium_m=0.05)
    assert weak.dg_kcal() > strong.dg_kcal()


def test_a_self_complementary_latch_is_refused_rather_than_approximated() -> None:
    assert is_self_complementary("GCGCGC")
    assert not is_self_complementary("GGCATTACCG")
    with pytest.raises(ValueError, match="self-complementary"):
        duplex("GCGCGC").melting_k()


def test_the_field_carries_the_factor_of_two() -> None:
    """p(+)/p(-) = exp(2h). Losing the two is a factor of two in every bias,
    and it would look like a plausible number. Checked through the Ising code
    itself rather than against a restatement of the formula."""
    import numpy as np

    latch = duplex("GCATGCAT")
    h = latch_field_kt(latch)
    states, p = distribution(Ising(h=np.array([h]), J=np.zeros((1, 1))))
    latched = p[states[:, 0] == 1][0]
    unlatched = p[states[:, 0] == -1][0]
    assert math.log(latched / unlatched) == pytest.approx(2 * h)


def test_a_tighter_latch_biases_towards_latched() -> None:
    weak = latch_field_kt(duplex("ATATAT" + "AT"))
    strong = latch_field_kt(duplex("GCGGCG" + "GC"))
    assert strong > weak > 0


def test_the_conformational_offset_shifts_the_field_by_half_itself() -> None:
    """It enters the same way the latch does, so a 2 kT cost of closing moves
    the field by 1 kT. Stage 0 measures it as an intercept."""
    latch = duplex("GCATGCAT")
    assert latch_field_kt(latch, conformational_kt=2.0) == pytest.approx(
        latch_field_kt(latch) - 1.0
    )


@pytest.mark.parametrize("sequence", CASES + candidate_latches())
def test_primer3_through_the_adapter_reproduces_the_published_table(sequence: str) -> None:
    """At the 1 M Na+ the table is stated at, over every latch the bracketing
    ladder can choose from, not just a handful."""
    ours = duplex(sequence, sodium_m=1.0)
    dh, ds = _published(sequence)
    assert ours.dh_kcal == pytest.approx(dh, abs=DH_TOLERANCE_KCAL)
    assert ours.ds_cal == pytest.approx(ds, abs=DS_TOLERANCE_CAL)
    assert ours.dg_kcal() == pytest.approx(dh - T37_K * ds / 1000.0, abs=DG_TOLERANCE_KCAL)


@pytest.mark.parametrize("sequence", ("GCATGCAT", "GACTAGTCATGA", "GATA"))
def test_the_design_buffer_reaches_primer3_as_magnesium(sequence: str) -> None:
    """The ladder's buffer: 12 mM Mg on top of the 1 M Na default. The
    published salt rule on the von Ahsen equivalent must come out, which it
    only does if the magnesium went in as magnesium and in mM."""
    ours = duplex(sequence, magnesium_m=DESIGN_MAGNESIUM_M)
    na_eq = sodium_equivalent_m(sodium_m=1.0, magnesium_m=DESIGN_MAGNESIUM_M)
    assert ours.sodium_equivalent_m == pytest.approx(na_eq)
    dh, ds = _published(sequence, na_eq_m=na_eq)
    assert ours.ds_cal == pytest.approx(ds, abs=DS_TOLERANCE_CAL)
    assert ours.dh_kcal == pytest.approx(dh, abs=DH_TOLERANCE_KCAL)


def test_magnesium_is_not_mistaken_for_sodium() -> None:
    """Negative control for the test above. 12 mM of magnesium is worth about
    416 mM of sodium; passed as 12 mM of sodium it would be a much weaker
    buffer, and this checks the difference is visible at all."""
    as_magnesium = duplex("GCATGCAT", sodium_m=0.0, magnesium_m=0.012)
    as_sodium = duplex("GCATGCAT", sodium_m=0.012, magnesium_m=0.0)
    equivalent = duplex("GCATGCAT", sodium_m=sodium_equivalent_m(magnesium_m=0.012))
    assert as_magnesium.ds_cal == pytest.approx(equivalent.ds_cal, abs=1e-6)
    assert as_sodium.dg_kcal() - as_magnesium.dg_kcal() > 0.5


@pytest.mark.parametrize("temperature_c", (25.0, 37.0, 60.0))
def test_free_energy_at_any_temperature_is_primer3s(temperature_c: float) -> None:
    """Only H and S are kept, and dG is rebuilt from them. That is exactly
    what primer3 does internally, so the rebuilt value must be its own number
    at whatever temperature primer3 is asked -- not merely close to it."""
    sequence = "GACTAGTCATGA"
    theirs = _p3.calc_heterodimer(
        sequence,
        reverse_complement(sequence),
        mv_conc=1000.0,
        dv_conc=12.0,
        dntp_conc=0.0,
        dna_conc=1000.0,
        temp_c=temperature_c,
    )
    ours = duplex(sequence, magnesium_m=0.012)
    assert ours.dg_kcal(temperature_c + 273.15) == pytest.approx(theirs.dg / 1000.0, abs=1e-9)


def test_the_ladder_field_is_the_published_one_up_to_the_known_offset() -> None:
    """The quantity the ladder is built from, at the ladder's own conditions:
    within the constant initiation offset above and nothing more."""
    na_eq = sodium_equivalent_m(sodium_m=1.0, magnesium_m=DESIGN_MAGNESIUM_M)
    t = DESIGN_TEMPERATURE_K
    for sequence in candidate_latches():
        dh, ds = _published(sequence, na_eq_m=na_eq)
        published = -((dh - t * ds / 1000.0) / (R_KCAL * t)) / 2.0
        ours = latch_field_kt(duplex(sequence, magnesium_m=DESIGN_MAGNESIUM_M), temperature_k=t)
        assert ours == pytest.approx(published, abs=0.03), sequence


@pytest.mark.parametrize("sequence", CASES)
def test_melting_matches_primer3_for_non_self_complementary_duplexes(sequence: str) -> None:
    ours = duplex(sequence, sodium_m=1.0)
    theirs = _p3.calc_heterodimer(
        sequence,
        reverse_complement(sequence),
        mv_conc=1000.0,
        dv_conc=0.0,
        dntp_conc=0.0,
        dna_conc=1000.0,
    )
    assert ours.melting_c(strand_m=1e-6) == pytest.approx(theirs.tm, abs=0.5)


def test_a_duplex_past_primer3s_limit_is_refused_rather_than_zeroed() -> None:
    """primer3 aligns at most 60 bp. Past that its result is zeros with
    `structure_found` still true -- a duplex of no energy, not an error -- so
    the length is refused before primer3 is asked."""
    at_limit = ("ACGGTCATTGCA" * 6)[:PRIMER3_MAX_LENGTH]
    assert duplex(at_limit).dh_kcal < -400.0
    with pytest.raises(ValueError, match="two-state"):
        duplex(at_limit + "A")


def test_rejects_things_that_are_not_dna() -> None:
    for bad in ("", "A", "ACGU", "ACGN", "acg t"):
        with pytest.raises(ValueError):
            duplex(bad)
    with pytest.raises(ValueError):
        gc_fraction("ACGU")


# ---------------------------------------------- arbitrary pairs and hairpins


def test_a_hybrid_of_a_sequence_with_its_complement_is_the_duplex() -> None:
    """`hybrid` answers about two arbitrary strands and `duplex` about a
    sequence and its complement, so on that input they must agree -- otherwise
    the buffer or the units differ between the two paths."""
    sequence = "GACTAGTCATGA"
    pair = hybrid(
        sequence,
        reverse_complement(sequence),
        magnesium_m=0.012,
        temperature_c=25.0,
        strand_m=1e-6,
    )
    ours = duplex(sequence, sodium_m=0.0, magnesium_m=0.012)
    assert pair.found
    assert pair.dg_kcal == pytest.approx(ours.dg_kcal(298.15), abs=0.01)
    assert pair.melting_c == pytest.approx(ours.melting_c(strand_m=1e-6), abs=1.0)


def test_strand_concentration_moves_a_melting_point_and_not_the_free_energy() -> None:
    """Which is why `Hybrid` records the concentration it was computed at: two
    melting points at different concentrations are not comparable."""
    sequence = "GACTAGTCATGA"
    kwargs = {"magnesium_m": 0.011, "temperature_c": 25.0}
    dilute = hybrid(sequence, reverse_complement(sequence), strand_m=2e-9, **kwargs)
    concentrated = hybrid(sequence, reverse_complement(sequence), strand_m=5e-8, **kwargs)
    assert concentrated.melting_c > dilute.melting_c + 5.0
    assert concentrated.dg_kcal == pytest.approx(dilute.dg_kcal, abs=1e-9)
    assert dilute.strand_m == 2e-9


def test_two_unrelated_strands_report_a_structure_that_melts_in_the_cold() -> None:
    """primer3 finds SOME alignment between almost any two strands; what
    matters is that it is cold. A caller comparing `found` alone would reject
    every sequence it was given."""
    pair = hybrid(
        "AACACATGACGA", "AACACATGACGA", magnesium_m=0.011, temperature_c=25.0, strand_m=2e-9
    )
    assert pair.melting_c < 0.0


def test_no_structure_reads_as_colder_than_any_threshold() -> None:
    """So that a "no hairpin" answer compares the same way as a weak one and
    no caller has to special-case it."""
    flat = hairpin("AAAAAAAAAAAA", magnesium_m=0.011, temperature_c=25.0)
    assert not flat.found
    assert flat.melting_c == NO_STRUCTURE_C
    assert flat.dg_kcal == 0.0


def test_a_hairpin_is_found_where_one_exists() -> None:
    """Negative control for the test above: the check has to be able to fire."""
    stem = "GCGCGCGCTTTTGCGCGCGC"
    folded = hairpin(stem, magnesium_m=0.011, temperature_c=25.0)
    assert folded.found
    assert folded.melting_c > 25.0


def test_a_hybrid_past_primer3s_alignment_limit_is_refused() -> None:
    """The same trap `duplex` guards: past 60 nt thal returns zeros with
    `structure_found` still true, so a long scaffold stretch must be split."""
    long = "ACGGTCATTGCA" * 6
    with pytest.raises(ValueError, match="alignment limit"):
        hybrid(long, "ACGT", magnesium_m=0.011, temperature_c=25.0, strand_m=1e-9)
    with pytest.raises(ValueError, match="alignment limit"):
        hairpin(long, magnesium_m=0.011, temperature_c=25.0)


def test_a_hybrid_needs_a_counterion_and_a_concentration() -> None:
    with pytest.raises(ValueError, match="counterion"):
        hybrid("ACGTACGT", "ACGTACGT", magnesium_m=0.0, temperature_c=25.0, strand_m=1e-9)
    with pytest.raises(ValueError, match="strand concentration"):
        hybrid("ACGTACGT", "ACGTACGT", magnesium_m=0.011, temperature_c=25.0, strand_m=0.0)


def test_a_hybrid_rejects_things_that_are_not_dna() -> None:
    for bad in ("", "ACGU", "acg t"):
        with pytest.raises(ValueError, match="not a DNA sequence"):
            hybrid(bad, "ACGTACGT", magnesium_m=0.011, temperature_c=25.0, strand_m=1e-9)

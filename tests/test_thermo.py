"""Nearest-neighbour thermodynamics, checked against an independent
implementation wherever one is installed.

primer3-py is GPLv2 and therefore an optional extra here, so these tests skip
in an environment without it. That is the point of having both: the parameter
table is transcribed from a paper, and a transcription error in one of thirty
numbers would be invisible in every internal consistency check.
"""

from __future__ import annotations

import math

import pytest

from dobladilo.hamiltonian.model import Ising, distribution
from dobladilo.sequence.thermo import (
    NEAREST_NEIGHBOUR,
    R_KCAL,
    T37_K,
    duplex,
    gc_fraction,
    is_self_complementary,
    latch_field_kt,
    reverse_complement,
    sodium_equivalent_m,
)

try:  # pragma: no cover - environment dependent
    import primer3 as _p3

    has_primer3 = True
except ImportError:  # pragma: no cover - environment dependent
    has_primer3 = False

needs_primer3 = pytest.mark.skipif(not has_primer3, reason="primer3-py is an optional extra")

#: Deliberately none of them self-complementary; that case is tested apart.
CASES = ("CGTTGA", "AGTCGTAC", "GGCATTACCG", "ACGGTCATTGCA", "TTTTTTTT", "GCGGCGGC")


def test_reverse_complement_is_an_involution() -> None:
    for s in CASES:
        assert reverse_complement(reverse_complement(s)) == s


def test_the_parameter_table_covers_every_dimer() -> None:
    """Ten entries cover sixteen dimers, because each stands for itself and
    its reverse complement. If one were missing, `duplex` would raise a
    KeyError on some ordinary sequence rather than on an obvious one."""
    bases = "ACGT"
    for a in bases:
        for b in bases:
            dimer = a + b
            assert dimer in NEAREST_NEIGHBOUR or reverse_complement(dimer) in NEAREST_NEIGHBOUR


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


@needs_primer3
@pytest.mark.parametrize("sequence", CASES)
def test_enthalpy_and_entropy_match_primer3(sequence: str) -> None:
    ours = duplex(sequence, sodium_m=1.0)
    theirs = _p3.calc_heterodimer(
        sequence,
        reverse_complement(sequence),
        mv_conc=1000.0,
        dv_conc=0.0,
        dntp_conc=0.0,
        dna_conc=1000.0,
    )
    assert ours.dh_kcal == pytest.approx(theirs.dh / 1000.0, abs=0.05)
    assert ours.ds_cal == pytest.approx(theirs.ds, abs=0.2)
    assert ours.dg_kcal() == pytest.approx(theirs.dg / 1000.0, abs=0.05)


@needs_primer3
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


def test_rejects_things_that_are_not_dna() -> None:
    for bad in ("", "A", "ACGU", "ACGN", "acg t"):
        with pytest.raises(ValueError):
            duplex(bad)
    with pytest.raises(ValueError):
        gc_fraction("ACGU")

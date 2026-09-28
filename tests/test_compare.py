"""The closed loop, and mostly the refusals that make it honest."""

from __future__ import annotations

import pytest

from dobladillo.compare import (
    AGREEMENT_SIGMA,
    Conditions,
    Observation,
    compare,
    deconvolve_tip,
    designed,
    half_height_broadening_nm,
)
from dobladillo.readings import Measured, When

SIM = Conditions(temperature_c=20.0, sodium_m=0.5, model="oxDNA2")
AFM = Conditions(temperature_c=23.0, magnesium_m=0.012, model="AFM")


def _sim(value: float, sd: float = 2.0, n: int = 200) -> Observation:
    return Observation("length_nm", value, "simulated_extent", "simulated", SIM, sd, n)


def _afm(value: float, sd: float = 6.0, n: int = 40) -> Observation:
    return Observation("length_nm", value, "afm_half_height", "measured", AFM, sd, n)


def _tip(radius_nm: float) -> Measured[float]:
    """A tip radius as the session record would supply it."""
    return Measured(
        value=radius_nm,
        quantity="tip_radius",
        source="test fixture",
        at=When(timestamp=0.0, basis="stated"),
        instrument="test",
    )


def test_broadening_follows_the_derived_geometry() -> None:
    # sqrt(R h - h^2/4): 10*2 - 1 = 19.
    assert half_height_broadening_nm(tip_radius_nm=10.0, feature_height_nm=2.0) == pytest.approx(
        19.0**0.5
    )


def test_a_blunter_tip_broadens_more() -> None:
    values = [
        half_height_broadening_nm(tip_radius_nm=r, feature_height_nm=2.0)
        for r in (5.0, 10.0, 20.0, 40.0)
    ]
    assert values == sorted(values)


def test_half_height_broadens_less_than_the_base() -> None:
    """Which is the entire reason `particles` measures at half height."""
    R, h = 10.0, 2.0
    half = half_height_broadening_nm(tip_radius_nm=R, feature_height_nm=h)
    base = (2 * R * h - h**2) ** 0.5
    assert half < base


def test_an_afm_footprint_is_not_compared_with_an_extent() -> None:
    """The refusal that matters most. A 10 nm tip puts 8.7 nm into a width;
    comparing the two definitions directly would hide that inside whatever
    disagreement was being investigated."""
    result = compare("length_nm", [_sim(188.0), _afm(197.0)])
    assert not result.compared_anything
    assert result.refused
    assert "not reconciled" in result.refused[0]


def test_nothing_compared_does_not_report_agreement() -> None:
    """`all([])` is True, so a comparison in which everything was refused would
    otherwise say it agrees -- indistinguishable from a real result."""
    result = compare("length_nm", [_sim(188.0), _afm(197.0)])
    assert result.agrees is False


def test_deconvolution_makes_the_pair_comparable_and_they_agree() -> None:
    fixed = deconvolve_tip(_afm(197.0), feature_height_nm=2.0, tip_radius_nm=_tip(10.0)).observation
    result = compare("length_nm", [_sim(188.0), fixed])
    assert result.compared_anything
    assert result.agrees


def test_deconvolution_costs_certainty() -> None:
    """An uncharacterised tip radius is the largest thing not known about the
    result, and a corrected width must not look better determined than the
    measurement it came from."""
    raw = _afm(197.0)
    fixed = deconvolve_tip(raw, feature_height_nm=2.0, tip_radius_nm=_tip(10.0)).observation
    assert fixed.uncertainty_nm > raw.uncertainty_nm


def test_deconvolution_refuses_an_observation_it_does_not_apply_to() -> None:
    with pytest.raises(ValueError, match="afm_half_height"):
        deconvolve_tip(_sim(188.0), feature_height_nm=2.0, tip_radius_nm=_tip(10.0))


def test_a_salt_mismatch_is_carried_not_dropped() -> None:
    """oxDNA2 has no explicit magnesium, so this mismatch can never be fixed.
    Refusing would make the module useless; ignoring it is the bug."""
    fixed = deconvolve_tip(_afm(190.0), feature_height_nm=2.0, tip_radius_nm=_tip(10.0)).observation
    result = compare("length_nm", [_sim(188.0), fixed])
    assert any("magnesium" in c for c in result.caveats)


def test_a_designed_value_needs_no_conditions() -> None:
    """A design is a specification, not a measurement. Demanding a salt from
    it would refuse the comparison the simulation exists to make."""
    result = compare("length_nm", [designed("length_nm", 191.0), _sim(188.4)])
    assert result.compared_anything
    assert result.agrees


def test_an_expected_systematic_is_not_a_disagreement() -> None:
    """With 200 frames the standard error is 0.15 nm, so a 2.6 nm end effect
    scores seventeen sigma. The statistics are answering the wrong question."""
    result = compare("length_nm", [designed("length_nm", 191.0), _sim(188.4)])
    pair = result.pairs[0]
    assert pair.sigma > 10
    assert pair.agrees
    assert pair.explained_by == "the expected systematic"


def test_a_real_shortfall_still_disagrees() -> None:
    """The allowance must not be so generous that a genuinely short fold
    passes. Eight per cent is not an end effect."""
    result = compare("length_nm", [designed("length_nm", 191.0), _sim(176.0)])
    assert not result.agrees
    assert result.pairs[0].explained_by == "neither"


def test_the_standard_error_is_on_the_mean_not_the_spread() -> None:
    """Conflating them makes every disagreement look significant."""
    spread = _sim(188.0, sd=2.0, n=100)
    assert spread.standard_error_nm == pytest.approx(0.2)
    unknown_n = Observation("length_nm", 188.0, "simulated_extent", "simulated", SIM, 2.0, None)
    assert unknown_n.standard_error_nm == pytest.approx(2.0)


def test_mixing_quantities_in_one_comparison_is_a_mistake() -> None:
    other = Observation("width_nm", 36.0, "simulated_extent", "simulated", SIM, 1.0, 10)
    with pytest.raises(ValueError, match="same quantity"):
        compare("length_nm", [_sim(188.0), other])


def test_agreement_threshold_is_what_it_says() -> None:
    a = _sim(100.0, sd=1.0, n=1)
    b = Observation("length_nm", 100.0 + AGREEMENT_SIGMA, "simulated_extent", "simulated", SIM)
    assert compare("length_nm", [a, b]).agrees
    c = Observation("length_nm", 100.0 + 3 * AGREEMENT_SIGMA, "simulated_extent", "simulated", SIM)
    assert not compare("length_nm", [a, c]).agrees

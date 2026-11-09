"""The geometry side is tested here; the mechanics side is tested against the
package that owns it, whenever that package is importable.

`nanoindent` is not on a package index and is not installed in CI, so the solver tests skip
there. That is deliberate: this project must not carry a second, unvalidated
copy of contact mechanics just so a test can run offline. What it does carry is
`MEASURED_FACTORS`, and the point of the skipped tests is that the day anyone
runs the suite with nanoindent present, a drifted pin fails loudly.
"""

from __future__ import annotations

import pytest

from dobladillo.constants import HELIX_DIAMETER_NM
from dobladillo.mechanics import (
    MEASURED_FACTORS,
    NANOINDENT_NOTE,
    Plate,
    Tip,
    correction,
    regime,
    thickness_ladder,
    thin_film_parameter,
)

has_nanoindent = True
try:  # pragma: no cover - environment dependent
    import nanoindent as _ni  # noqa: F401
except ImportError:  # pragma: no cover - environment dependent
    has_nanoindent = False

needs_nanoindent = pytest.mark.skipif(
    not has_nanoindent, reason="LorenaRedondo/nanoindent is not installed here"
)

TIP = Tip(radius_nm=10.0, depth_nm=0.4)


def test_thickness_is_layers_times_helix_diameter() -> None:
    assert Plate(layers=3, footprint_nm=100.0).thickness_nm == 3 * HELIX_DIAMETER_NM


def test_plate_rejects_impossible_geometry() -> None:
    with pytest.raises(ValueError, match="at least one layer"):
        Plate(layers=0, footprint_nm=100.0)
    with pytest.raises(ValueError, match="footprint"):
        Plate(layers=1, footprint_nm=0.0)


def test_tip_rejects_impossible_geometry() -> None:
    with pytest.raises(ValueError, match="radius"):
        Tip(radius_nm=0.0, depth_nm=0.4)
    with pytest.raises(ValueError, match="depth"):
        Tip(radius_nm=10.0, depth_nm=-1.0)


def test_thin_film_parameter_matches_its_definition() -> None:
    plate = Plate(layers=1, footprint_nm=100.0)
    # sqrt(10 * 0.4) / 2.0 = 2 / 2 = 1
    assert thin_film_parameter(plate, TIP) == pytest.approx(1.0)


def test_thicker_plates_have_smaller_chi() -> None:
    chis = [thin_film_parameter(p, TIP) for p in thickness_ladder()]
    assert chis == sorted(chis, reverse=True)


@pytest.mark.parametrize(
    ("chi", "expected"),
    [
        (0.01, "half-space"),
        (0.049, "half-space"),
        (0.05, "closed-form"),
        (0.3, "closed-form"),
        (0.5, "finite-element"),
        (1.0, "finite-element"),
    ],
)
def test_regime_boundaries(chi: float, expected: str) -> None:
    assert regime(chi) == expected


def test_no_origami_plate_reaches_the_half_space_regime() -> None:
    """The whole argument for this module. If a plate ever did land in the
    half-space regime, a Hertz fit on it would be defensible and the
    calibration experiment would lose its point."""
    assert all(regime(thin_film_parameter(p, TIP)) != "half-space" for p in thickness_ladder())


def test_ladder_varies_only_the_layer_count() -> None:
    ladder = thickness_ladder()
    assert len({p.footprint_nm for p in ladder}) == 1
    assert len({p.layers for p in ladder}) == len(ladder)


def test_the_import_error_explains_where_to_get_the_package() -> None:
    assert "nanoindent" in NANOINDENT_NOTE
    assert "optional" in NANOINDENT_NOTE


@needs_nanoindent
@pytest.mark.parametrize("layers", sorted(MEASURED_FACTORS))
def test_pinned_factors_still_hold(layers: int) -> None:
    plate = Plate(layers=layers, footprint_nm=100.0)
    assert correction(plate, TIP).factor == pytest.approx(MEASURED_FACTORS[layers], abs=0.01)


@needs_nanoindent
def test_correction_is_independent_of_the_sample_modulus() -> None:
    """Not a property of our code but of linear elasticity, and the reason a
    plate of designed thickness calibrates an AFM without anyone knowing what
    DNA's modulus is. Worth a test because the day it stops holding, every
    number this module reports changes meaning."""
    from dobladillo.mechanics import plate as mod

    plate = Plate(layers=1, footprint_nm=100.0)
    baseline = correction(plate, TIP).factor
    original = mod._PROBE_MODULUS_MPA
    try:
        mod._PROBE_MODULUS_MPA = 3 * original  # type: ignore[misc]
        assert correction(plate, TIP).factor == pytest.approx(baseline, rel=1e-4)
    finally:
        mod._PROBE_MODULUS_MPA = original  # type: ignore[misc]


@needs_nanoindent
def test_an_unbonded_plate_is_markedly_softer() -> None:
    plate = Plate(layers=1, footprint_nm=100.0)
    bonded = correction(plate, TIP, substrate="bonded").factor
    unbonded = correction(plate, TIP, substrate="unbonded").factor
    assert unbonded < bonded / 1.5


@needs_nanoindent
def test_closed_forms_diverge_as_the_film_thins() -> None:
    spreads = [correction(p, TIP).closed_form_spread for p in thickness_ladder()]
    assert spreads == sorted(spreads, reverse=True)

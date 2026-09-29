"""Lateral resolution against closed forms and against imaged pairs.

The predicted resolution is checked two ways. Against geometry: for a
spherical tip and cylindrical features the answer has a closed form, and for
a paraboloid tip and small features it is Bustamante and Keller's. And
against the thing it predicts: pairs rendered through the same tip, with
noise, are resolved above the predicted spacing and not well below it.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from dobladillo.calibration.resolution import (
    bustamante_keller_nm,
    lateral_resolution,
    pair_resolved,
    pixel_noise,
)
from dobladillo.calibration.tip import dilate, paraboloid_tip, sphere_cone_tip


def sphere_cylinder_nm(radius: float, height: float, dip: float) -> float:
    """Closed form: a sphere of radius R images a cylinder of radius a as a
    circle of radius R + a, so the dip between two reaches dz at
    d = 2 sqrt(2 (R + a) dz - dz^2)."""
    total = radius + height / 2
    return 2 * math.sqrt(2 * total * dip - dip**2)


@pytest.mark.parametrize("radius", [5.0, 10.0, 20.0])
def test_resolution_matches_the_sphere_and_cylinder_closed_form(radius: float) -> None:
    pixel = 0.5
    tip = sphere_cone_tip(radius, pixel, 61, half_angle_deg=30.0)
    result = lateral_resolution(tip, pixel, 0.1)
    assert result.resolvable
    expected = sphere_cylinder_nm(radius, 2.0, 0.3)
    assert result.value_nm == pytest.approx(expected, rel=0.01)
    assert result.along_x_nm == pytest.approx(result.along_y_nm)  # a round tip


@pytest.mark.parametrize("radius", [5.0, 10.0, 20.0])
def test_resolution_agrees_with_bustamante_and_keller(radius: float) -> None:
    """Features small against the tip are the point features their formula
    assumes; a paraboloid is the tip it assumes."""
    pixel = 0.25
    result = lateral_resolution(
        paraboloid_tip(radius, pixel, 121), pixel, 0.02, feature_height_nm=0.2
    )
    formula = bustamante_keller_nm(tip_radius_nm=radius, dip_nm=0.06)
    assert result.value_nm == pytest.approx(formula, rel=0.02)


def test_the_formula_itself() -> None:
    assert bustamante_keller_nm(tip_radius_nm=10.0, dip_nm=0.5) == pytest.approx(
        math.sqrt(8 * 10.0 * 0.5)
    )
    assert bustamante_keller_nm(tip_radius_nm=10.0, dip_nm=0.5, height_step_nm=1.0) > (
        bustamante_keller_nm(tip_radius_nm=10.0, dip_nm=0.5)
    )


def test_resolution_grows_with_tip_radius() -> None:
    pixel = 0.5
    values = [
        lateral_resolution(sphere_cone_tip(r, pixel, 81), pixel, 0.1).value_nm
        for r in (2.0, 5.0, 10.0, 20.0, 30.0)
    ]
    assert values == sorted(values)
    assert values[-1] > 2 * values[0]


def test_resolution_grows_with_noise() -> None:
    tip = sphere_cone_tip(10.0, 0.5, 61)
    quiet = lateral_resolution(tip, 0.5, 0.05).value_nm
    loud = lateral_resolution(tip, 0.5, 0.2).value_nm
    assert loud > quiet


def render_pair(tip: np.ndarray, pixel: float, spacing: float, rows: int = 40) -> np.ndarray:
    """Two lines of 2 nm circular cross-section along the rows, imaged."""
    cols = int(80 / pixel)
    x = (np.arange(cols) - cols / 2) * pixel

    def line(centre: float) -> np.ndarray:
        offset = x - centre
        return np.where(np.abs(offset) <= 1.0, 1.0 + np.sqrt(np.maximum(1.0 - offset**2, 0)), 0.0)

    surface = np.maximum(line(-spacing / 2), line(spacing / 2))
    return dilate(np.tile(surface, (rows, 1)), tip)


def test_a_pair_above_the_predicted_resolution_is_resolved_and_one_below_is_not() -> None:
    """Render pairs through the tip, add the noise the prediction assumed,
    and ask `pair_resolved` of every scan line.

    Measured on these fixtures (60 lines, five noise draws, tips of 5, 10
    and 20 nm): 100% resolved at 1.5 times the predicted spacing, 25-53% at
    the predicted spacing itself, at most 3% at half of it.
    """
    pixel, noise = 0.5, 0.1
    rng = np.random.default_rng(0)
    for radius in (5.0, 10.0, 20.0):
        tip = sphere_cone_tip(radius, pixel, 61)
        predicted = lateral_resolution(tip, pixel, noise).along_x_nm

        def fraction_resolved(spacing: float, tip: np.ndarray = tip) -> float:
            image = render_pair(tip, pixel, spacing, rows=60)
            image = image + rng.normal(0, noise, image.shape)
            return float(np.mean([pair_resolved(line, noise).resolved for line in image]))

        assert fraction_resolved(1.5 * predicted) >= 0.95
        assert 0.1 <= fraction_resolved(predicted) <= 0.9
        assert fraction_resolved(0.5 * predicted) <= 0.1


def test_pair_resolved_reports_the_dip_and_the_peaks() -> None:
    profile = np.array([0.0, 0.1, 1.8, 2.0, 1.2, 1.9, 2.0, 0.3, 0.0])
    result = pair_resolved(profile, 0.1, pixel_nm=0.5)
    assert result.resolved
    assert result.valley_px == 4
    assert result.dip_nm == pytest.approx(0.8)
    assert result.peaks_px == (3, 6)
    assert result.separation_nm == pytest.approx(1.5)
    assert result.dip_uncertainty_nm == pytest.approx(0.1 * math.sqrt(2))
    json.dumps(result.as_dict())


def test_pair_resolved_ignores_the_substrate_beside_a_single_feature() -> None:
    """A single bump with a noise spike on the floor next to it is not a
    pair: the valley between them is not between two features."""
    profile = np.array([0.0, 0.5, 0.0, 0.0, 1.5, 2.0, 1.5, 0.0, -0.4, 0.0])
    assert not pair_resolved(profile, 0.1).resolved


def test_noise_larger_than_the_features_cannot_resolve_anything() -> None:
    result = lateral_resolution(sphere_cone_tip(10.0, 1.0, 21), 1.0, 1.0)
    assert not result.resolvable
    assert math.isinf(result.value_nm)
    assert "deeper than" in result.reason
    assert json.loads(json.dumps(result.as_dict()))["value_nm"] is None


def test_a_tip_array_too_small_to_show_the_dip_is_flagged() -> None:
    """A very blunt tip in a small array: the dip never reaches the depth
    inside it, and the answer is 'not determined', not a number."""
    result = lateral_resolution(paraboloid_tip(500.0, 1.0, 7), 1.0, 0.3)
    assert not result.resolvable
    assert "edge of the tip array" in result.reason


def test_uncertainty_carries_anisotropy_and_noise() -> None:
    """An elliptical tip resolves differently along the two axes, and an
    uncertain noise level widens the answer."""
    pixel = 0.5
    offsets = (np.arange(61) - 30) * pixel
    tip = -(offsets[None, :] ** 2 / (2 * 8.0) + offsets[:, None] ** 2 / (2 * 16.0))
    result = lateral_resolution(tip, pixel, 0.1, noise_uncertainty_nm=0.02)
    assert result.along_x_nm < result.along_y_nm
    assert result.components_nm["anisotropy"] == pytest.approx(
        0.5 * (result.along_y_nm - result.along_x_nm)
    )
    assert result.components_nm["noise"] > 0
    assert result.uncertainty_nm == pytest.approx(
        math.hypot(result.components_nm["anisotropy"], result.components_nm["noise"])
    )


def test_pixel_noise_is_recovered_through_features_and_line_offsets() -> None:
    rng = np.random.default_rng(2)
    sigma = 0.12
    image = np.zeros((256, 256))
    image[40:80, 30:200] = 2.0  # a sheet
    image += rng.normal(0, 0.3, (256, 1))  # every line its own offset
    image += rng.normal(0, sigma, image.shape)
    noise = pixel_noise(image)
    assert abs(noise.sigma_nm - sigma) <= 3 * noise.uncertainty_nm
    assert noise.uncertainty_nm < 0.01 * sigma * 5


def test_bustamante_keller_reproduces_the_articles_worked_example() -> None:
    """Box 1 of Bustamante & Keller (1995): a 10 nm paraboloid tip and a 0.5 nm
    dimple resolve equal features 6.4 nm apart (6.32 unrounded). Its second
    example, 12.5 nm for a 2 nm height difference, does not follow from its own
    equation (10.2 nm); the equation is what is implemented."""
    import pytest

    from dobladillo.calibration.resolution import bustamante_keller_nm

    assert bustamante_keller_nm(tip_radius_nm=10.0, dip_nm=0.5) == pytest.approx(6.4, abs=0.1)
    assert bustamante_keller_nm(
        tip_radius_nm=10.0, dip_nm=0.5, height_step_nm=2.0
    ) == pytest.approx(10.23, abs=0.01)

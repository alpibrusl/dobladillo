"""Tip morphology against tips and surfaces whose shapes were put in by hand.

Every test here builds a surface, images it with a KNOWN tip through
`dilate`, and asks the calibration code to get the tip back. The properties
tested are the ones the method promises, not just numbers:

- erosion of an image is never below the surface, and equals it wherever the
  tip touched;
- a blind estimate is never sharper than the true tip (an outer bound), and
  with sharp features and no noise it IS the true tip;
- a radius comes with an uncertainty that covers the truth;
- and when the image cannot constrain the tip, the answer says so instead of
  returning a confident radius.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from dobladillo.calibration.tip import (
    ApexRadius,
    apex_radius,
    blind_tip,
    dilate,
    erode,
    known_surface_tip,
    paraboloid_tip,
    sphere_cone_tip,
)
from dobladillo.compare.corrections import deconvolve_tip
from dobladillo.compare.observation import Conditions, Observation
from dobladillo.imaging.heightmap import HeightMap

PIXEL_NM = 1.0

#: Heights of the blocks on the commercial 3D AFM reference (a staircase for
#: tip characterisation, Kolbeck et al., Nano Lett. 2023), used here only as
#: plausible step heights for a synthetic staircase.
STAIRCASE_NM = (2.5, 5.0, 12.5, 20.0)


def spikes(size: int, count: int, seed: int, low: float = 25.0, high: float = 40.0) -> np.ndarray:
    """Single-pixel spikes, far sharper than any tip, on a flat floor."""
    rng = np.random.default_rng(seed)
    surface = np.zeros((size, size))
    for _ in range(count):
        i, j = rng.integers(0, size, 2)
        surface[i, j] = max(surface[i, j], rng.uniform(low, high))
    return surface


def staircase(size: int = 200, block: int = 20) -> np.ndarray:
    """Flat-topped square blocks of the staircase heights, well apart."""
    surface = np.zeros((size, size))
    corners = [(30, 30), (30, 130), (130, 30), (130, 130)]
    for (r, c), h in zip(corners, STAIRCASE_NM, strict=True):
        surface[r : r + block, c : c + block] = h
    return surface


def tip_of(kind: str, radius: float, size: int = 31) -> np.ndarray:
    if kind == "paraboloid":
        return paraboloid_tip(radius, PIXEL_NM, size)
    return sphere_cone_tip(radius, PIXEL_NM, size)


# --------------------------------------------------------------- morphology


def test_the_image_of_a_spike_is_the_tip() -> None:
    """The convention, pinned: a tip is drawn as a sharp spike would image it."""
    tip = sphere_cone_tip(8.0, PIXEL_NM, 15)
    surface = np.zeros((41, 41))
    surface[20, 20] = 30.0
    image = dilate(surface, tip)
    assert np.allclose(image[13:28, 13:28], 30.0 + tip[::-1, ::-1])
    assert image[20, 20] == 30.0


def test_tip_models_follow_the_convention() -> None:
    for tip in (paraboloid_tip(10, 1.0, 21), sphere_cone_tip(10, 1.0, 21)):
        assert tip[10, 10] == 0.0
        assert tip.max() == 0.0
        assert np.allclose(tip, tip.T) and np.allclose(tip, tip[::-1, ::-1])
    # The sphere meets the cone without a step or a kink: sampled finely, no
    # step between neighbours exceeds the cone's own slope.
    fine = 0.05
    row = sphere_cone_tip(10.0, fine, 801, half_angle_deg=20.0)[400]
    assert np.abs(np.diff(row)).max() <= fine / np.tan(np.radians(20.0)) + 1e-9


@pytest.mark.parametrize("bad", [np.zeros((4, 5)), -np.ones((5, 5)), np.ones((5, 5))])
def test_a_malformed_tip_is_refused(bad: np.ndarray) -> None:
    with pytest.raises(ValueError):
        dilate(np.zeros((10, 10)), bad)


def test_erosion_is_exact_where_the_tip_touched_and_an_upper_bound_elsewhere() -> None:
    """Dilate then erode: the reconstruction never dips below the surface,
    and equals it exactly at every point some apex position touched.

    "Touched" is computed from the definition, independently of `erode`: a
    surface point y is touched when, for some apex position x, the tip
    surface over y sits exactly on it, I(x) - t(y - x) = s(y).
    """
    rng = np.random.default_rng(7)
    surface = spikes(96, 25, seed=3, low=3.0, high=15.0)
    surface[60:80, 10:40] += 6.0  # a plateau with vertical walls
    surface += 0.5 * np.sin(np.arange(96) / 7.0)[None, :]  # a gentle wave
    surface += rng.normal(0, 0.05, surface.shape)
    tip = sphere_cone_tip(6.0, PIXEL_NM, 15)
    image = dilate(surface, tip)
    reconstructed = erode(image, tip)

    assert (reconstructed >= surface - 1e-9).all()

    a = 7
    padded = np.pad(image, a, constant_values=np.nan)
    touched = np.zeros(surface.shape, dtype=bool)
    rows, cols = surface.shape
    for i in range(15):
        for j in range(15):
            # apex at y - v, with v = (i - a, j - a)
            apex = padded[2 * a - i : 2 * a - i + rows, 2 * a - j : 2 * a - j + cols]
            touched |= np.abs(apex - tip[i, j] - surface) < 1e-9
    assert touched.mean() > 0.3, "the fixture should be mostly reachable"
    assert np.abs(reconstructed[touched] - surface[touched]).max() < 1e-9
    # And the test is not vacuous: between features the tip never reached.
    assert (reconstructed[~touched] > surface[~touched] + 1e-6).any()


# ------------------------------------------------------------ blind estimate


@pytest.mark.parametrize("kind", ["paraboloid", "sphere_cone"])
@pytest.mark.parametrize("radius", [5.0, 10.0, 20.0])
def test_blind_tip_recovers_a_known_tip_exactly_without_noise(kind: str, radius: float) -> None:
    """Sharp spikes, no noise, threshold 0: the estimate is the tip itself,
    down to the depth of the shortest spike, and never sharper than it."""
    true = tip_of(kind, radius)
    image = HeightMap(dilate(spikes(256, 60, seed=1), true), PIXEL_NM)
    estimate = blind_tip(image, 31, 0.0)

    assert estimate.converged and estimate.informative
    assert (estimate.heights_nm >= true - 1e-9).all(), "outer bound"
    reachable = true >= -25.0  # the shortest spike is 25 nm tall
    assert np.abs(estimate.heights_nm - true)[reachable].max() < 1e-6

    measured = estimate.apex_radius()
    assert measured.determined
    assert abs(measured.radius_nm - radius) <= measured.uncertainty_nm


@pytest.mark.parametrize("kind", ["paraboloid", "sphere_cone"])
@pytest.mark.parametrize("radius", [5.0, 10.0, 20.0])
@pytest.mark.parametrize("noise", [0.05, 0.1])
def test_blind_tip_stays_an_outer_bound_under_noise(kind: str, radius: float, noise: float) -> None:
    """With noise and a threshold of 5 sigma the estimate is still never
    sharper than the truth, and its radius is an honest overestimate.

    Stated tolerance: the recovered radius lies between the true radius
    minus its uncertainty and 1.6 times the true radius. Measured on these
    fixtures: +11% to +33% for sphere-on-cone tips, +34% to +53% for
    paraboloids. The excess is the price of the threshold, which admits
    contacts near the apex and widens the estimate sideways.
    """
    true = tip_of(kind, radius)
    clean = dilate(spikes(256, 60, seed=1), true)
    for seed in range(2):
        noisy = clean + np.random.default_rng(seed).normal(0, noise, clean.shape)
        estimate = blind_tip(HeightMap(noisy, PIXEL_NM), 31, 5 * noise)
        assert (estimate.heights_nm >= true - 1e-9).all(), "outer bound"
        measured = estimate.apex_radius()
        assert measured.determined
        assert radius - measured.uncertainty_nm <= measured.radius_nm <= 1.6 * radius


def test_a_threshold_below_the_noise_breaks_the_bound() -> None:
    """Why the threshold is 5 sigma and not 3: at 3 sigma the noise wins.

    A negative control for the threshold advice in the docstring. Pixel
    noise makes the image locally sharper than the tip, a too-small
    threshold lets that through, and the error compounds over passes into a
    tip far SHARPER than the real one -- the one thing an outer bound must
    never be.
    """
    true = sphere_cone_tip(10.0, PIXEL_NM, 31)
    clean = dilate(spikes(256, 60, seed=1), true)
    noisy = clean + np.random.default_rng(0).normal(0, 0.1, clean.shape)
    estimate = blind_tip(HeightMap(noisy, PIXEL_NM), 31, 0.3)
    assert (true - estimate.heights_nm).max() > 5.0


def test_blind_tip_on_a_featureless_image_says_it_learned_nothing() -> None:
    """The negative control: flat and noisy, so nothing constrains the tip.
    The estimate stays flat, is flagged, and yields no radius -- not a large
    one."""
    flat = np.random.default_rng(3).normal(0, 0.1, (256, 256))
    estimate = blind_tip(HeightMap(flat, PIXEL_NM), 21, 0.5)
    assert not estimate.informative
    assert estimate.rim_depth_nm < 1.0
    assert "did not constrain" in estimate.note
    measured = estimate.apex_radius()
    assert not measured.determined
    assert np.isnan(measured.radius_nm)
    record = json.loads(json.dumps(estimate.as_dict()))
    assert record["informative"] is False


def test_blind_tip_learns_nothing_from_a_staircase_of_flat_blocks() -> None:
    """Flat-topped blocks have no local maximum narrower than the tip, so a
    flat punch explains their image and the blind bound cannot move. That
    is what `known_surface_tip` is for; blind estimation says so."""
    true = sphere_cone_tip(10.0, PIXEL_NM, 21)
    image = HeightMap(dilate(staircase(), true), PIXEL_NM)
    estimate = blind_tip(image, 21, 0.0)
    assert not estimate.informative


def test_blind_tip_is_fast_enough_on_a_full_scan() -> None:
    """512 x 512 with a 31 px tip. About a second here; the bound is generous
    so a slow machine does not fail it, but a return to every-point
    processing (tens of times slower) would."""
    true = sphere_cone_tip(10.0, PIXEL_NM, 31)
    clean = dilate(spikes(512, 150, seed=4), true)
    noisy = clean + np.random.default_rng(5).normal(0, 0.1, clean.shape)
    start = time.perf_counter()
    estimate = blind_tip(HeightMap(noisy, PIXEL_NM), 31, 0.5)
    assert time.perf_counter() - start < 20.0
    assert estimate.converged
    assert (estimate.heights_nm >= true - 1e-9).all()
    measured = estimate.apex_radius()
    assert 10.0 - measured.uncertainty_nm <= measured.radius_nm <= 1.6 * 10.0


# ------------------------------------------------------------- known surface


def test_known_surface_tip_recovers_the_tip_from_a_staircase() -> None:
    """Given the blocks' geometry, their edges and corners give the tip down
    to the tallest step. Exact without noise; an outer bound with it."""
    true = sphere_cone_tip(10.0, PIXEL_NM, 31)
    surface = staircase()
    image = dilate(surface, true)
    estimate = known_surface_tip(HeightMap(image, PIXEL_NM), surface, size_px=31)
    assert estimate.informative
    assert (estimate.heights_nm >= true - 1e-9).all()
    within = true >= -max(STAIRCASE_NM)
    assert np.abs(estimate.heights_nm - true)[within].max() < 1e-9
    # The largest consistent tip reproduces the image.
    assert np.allclose(dilate(surface, estimate.heights_nm)[20:-20, 20:-20], image[20:-20, 20:-20])

    noisy = image + np.random.default_rng(1).normal(0, 0.1, image.shape)
    rough = known_surface_tip(HeightMap(noisy, PIXEL_NM), surface, size_px=31, threshold_nm=0.5)
    assert (rough.heights_nm >= true - 1e-9).all()
    measured = rough.apex_radius()
    assert measured.determined
    assert 10.0 - measured.uncertainty_nm <= measured.radius_nm <= 1.6 * 10.0


def test_known_surface_tip_refuses_an_unregistered_surface() -> None:
    with pytest.raises(ValueError, match="registered"):
        known_surface_tip(HeightMap(np.zeros((50, 50)), 1.0), np.zeros((40, 50)), size_px=11)


# --------------------------------------------------------------- apex radius


@pytest.mark.parametrize("kind", ["paraboloid", "sphere_cone"])
@pytest.mark.parametrize("radius", [5.0, 10.0, 20.0])
def test_apex_radius_recovers_a_known_radius(kind: str, radius: float) -> None:
    """Noise-free: within one standard uncertainty. Noisy (0.05 nm on every
    tip pixel, 40 draws): always within two, and within one for a fraction
    of draws that shows the uncertainty is neither understated (too few)
    nor padded (all of them). Measured: 48-78% within one."""
    tip = tip_of(kind, radius)
    clean = apex_radius(tip, PIXEL_NM)
    assert clean.determined
    assert abs(clean.radius_nm - radius) <= clean.uncertainty_nm
    assert clean.uncertainty_nm < 0.15 * radius

    within_one = 0
    for seed in range(40):
        noisy = tip + np.random.default_rng(seed).normal(0, 0.05, tip.shape)
        noisy = np.minimum(noisy - noisy[15, 15], 0.0)
        measured = apex_radius(noisy, PIXEL_NM)
        assert measured.determined
        error = abs(measured.radius_nm - radius)
        assert error <= 2 * measured.uncertainty_nm
        within_one += error <= measured.uncertainty_nm
    assert 0.4 <= within_one / 40 <= 0.95


def test_apex_radius_names_its_depth_convention() -> None:
    measured = apex_radius(sphere_cone_tip(10.0, PIXEL_NM, 31), PIXEL_NM, depth_nm=3.0)
    record = measured.as_dict()
    assert record["depth_nm"] == 3.0
    assert "below the apex" in record["convention"]
    assert set(record["components_nm"]) == {"model", "statistical", "depth"}


def test_apex_radius_refuses_a_band_that_leaves_the_array() -> None:
    """A 40 nm tip in an 11 px array is not resolved to 2 nm deep inside it."""
    measured = apex_radius(sphere_cone_tip(40.0, PIXEL_NM, 11), PIXEL_NM)
    assert not measured.determined
    assert "edge of the tip array" in measured.reason


def test_a_flat_tip_has_no_radius_and_cannot_become_a_measurement() -> None:
    measured = apex_radius(np.zeros((21, 21)), PIXEL_NM)
    assert not measured.determined
    with pytest.raises(ValueError, match="no radius"):
        measured.as_measured("flat")


def test_a_measured_radius_feeds_the_tip_deconvolution() -> None:
    """The point of the exercise: a radius from an image, as a `Measured`,
    is what `deconvolve_tip` accepts where it refuses the one on the box."""
    true = sphere_cone_tip(10.0, PIXEL_NM, 31)
    estimate = blind_tip(HeightMap(dilate(spikes(256, 60, seed=1), true), PIXEL_NM), 31, 0.0)
    measured: ApexRadius = estimate.apex_radius()
    reading = measured.as_measured("synthetic spikes, blind estimate")
    width = Observation(
        quantity="width",
        value_nm=45.0,
        definition="afm_half_height",
        origin="measured",
        conditions=Conditions(model="synthetic"),
        uncertainty_nm=1.0,
    )
    corrected = deconvolve_tip(width, feature_height_nm=2.0, tip_radius_nm=reading)
    assert corrected.observation.value_nm < 45.0
    assert corrected.tip_radius.uncertainty == pytest.approx(measured.uncertainty_nm)

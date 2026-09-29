"""Invariants that must hold for ANY input, checked on generated ones (Hypothesis).

The example tests elsewhere pin known answers. These state what the code
promises in general -- an erosion is never below the surface, a rigid
rotation keeps distances, a noise estimate scales with the noise -- and let
Hypothesis search for an input that breaks it, shrinking any failure to the
smallest example. They test the numpy code itself, which is what a proof
about the mathematics could not.
"""

from __future__ import annotations

import string

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from dobladillo.calibration.tip import blind_tip, dilate, erode, paraboloid_tip
from dobladillo.imaging.heightmap import HeightMap

FAST = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
SLOW = settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])

heights = st.floats(min_value=-5.0, max_value=40.0, allow_nan=False, allow_infinity=False)


@st.composite
def tips(draw: st.DrawFn, size: int = 5) -> np.ndarray:
    """A valid tip in the module's convention: apex 0 at the centre, <= 0 elsewhere."""
    tip = draw(
        hnp.arrays(np.float64, (size, size), elements=st.floats(-20.0, 0.0, allow_nan=False))
    )
    tip[size // 2, size // 2] = 0.0
    return tip


surfaces = hnp.arrays(np.float64, (14, 14), elements=heights)


# ------------------------------------------------------------ grey-scale morphology


@FAST
@given(surface=surfaces, tip=tips())
def test_erosion_of_an_image_is_never_below_the_surface_that_made_it(
    surface: np.ndarray, tip: np.ndarray
) -> None:
    """Villarrubia's reconstruction is an upper bound on the surface, everywhere."""
    reconstructed = erode(dilate(surface, tip), tip)
    assert np.all(reconstructed >= surface - 1e-9)


@FAST
@given(surface=surfaces, tip=tips())
def test_opening_never_raises_an_image(surface: np.ndarray, tip: np.ndarray) -> None:
    """Dilating the reconstruction gives back no more than the image: (I - t) + t <= I."""
    image = dilate(surface, tip)
    assert np.all(dilate(erode(image, tip), tip) <= image + 1e-9)


@FAST
@given(surface=surfaces, tip=tips(), shift=heights)
def test_dilation_commutes_with_a_height_offset(
    surface: np.ndarray, tip: np.ndarray, shift: float
) -> None:
    assert np.allclose(dilate(surface + shift, tip), dilate(surface, tip) + shift)


@SLOW
@given(
    radius=st.floats(3.0, 20.0),
    spikes=st.lists(
        st.tuples(st.integers(16, 63), st.integers(16, 63), st.floats(15.0, 40.0)),
        min_size=3,
        max_size=12,
    ),
)
def test_a_blind_tip_is_never_sharper_than_the_true_one(
    radius: float, spikes: list[tuple[int, int, float]]
) -> None:
    """The outer-bound guarantee, noise-free, for any spike field and tip radius."""
    true = paraboloid_tip(radius, 1.0, 15)
    surface = np.zeros((80, 80))
    for i, j, h in spikes:
        surface[i, j] = max(surface[i, j], h)
    estimate = blind_tip(HeightMap(dilate(surface, true), 1.0), 15, 0.0)
    assert np.all(estimate.heights_nm >= true - 1e-9)


# ------------------------------------------------------------ noise estimate


@FAST
@given(
    scale=st.floats(0.1, 10.0),
    slope=st.floats(-2.0, 2.0),
    offsets=hnp.arrays(np.float64, 64, elements=st.floats(-5.0, 5.0)),
    seed=st.integers(0, 2**16),
)
def test_pixel_noise_scales_with_the_noise_and_ignores_slopes_and_line_offsets(
    scale: float, slope: float, offsets: np.ndarray, seed: int
) -> None:
    from dobladillo.calibration.resolution import pixel_noise

    noise = np.random.default_rng(seed).normal(0.0, 1.0, (64, 64))
    ramp = slope * np.arange(64)[None, :] + offsets[:, None]
    base = pixel_noise(noise).sigma_nm
    assert pixel_noise(scale * noise + ramp).sigma_nm == pytest.approx(scale * base, rel=1e-6)


# ------------------------------------------------------------ rigid folding


@FAST
@given(
    points=hnp.arrays(np.float64, (12, 3), elements=st.floats(-50.0, 50.0)),
    axis=hnp.arrays(np.float64, 3, elements=st.floats(-1.0, 1.0)).filter(
        lambda a: np.linalg.norm(a) > 0.1
    ),
    point=hnp.arrays(np.float64, 3, elements=st.floats(-20.0, 20.0)),
    angle=st.floats(-np.pi, np.pi),
)
def test_folding_an_arm_keeps_its_shape_and_its_unit_vectors(
    points: np.ndarray, axis: np.ndarray, point: np.ndarray, angle: float
) -> None:
    from dobladillo.sim.fold import POSITION, rotate_particles

    rng = np.random.default_rng(0)
    data = np.zeros((12, 15))
    data[:, POSITION] = points
    a1 = rng.normal(size=(12, 3))
    data[:, 3:6] = a1 / np.linalg.norm(a1, axis=1, keepdims=True)
    arm = list(range(6))
    out = rotate_particles(data, arm, point=point, axis=axis, angle_rad=angle)

    def distances(xyz: np.ndarray) -> np.ndarray:
        return np.linalg.norm(xyz[:, None, :] - xyz[None, :, :], axis=-1)

    assert np.allclose(distances(out[arm, POSITION]), distances(points[arm]), atol=1e-8)
    assert np.allclose(np.linalg.norm(out[:, 3:6], axis=1), 1.0)
    assert np.array_equal(out[6:], data[6:])  # the rest of the structure does not move


# ------------------------------------------------------------ records


names = st.text(string.ascii_letters + string.digits + "-_", min_size=1, max_size=12)


@FAST
@given(
    coordinates=st.lists(
        st.tuples(st.floats(-200.0, 200.0), st.floats(-200.0, 200.0)),
        min_size=3,
        max_size=20,
    ),
    ux=st.floats(0.0, 0.2),
    uy=st.floats(0.0, 0.2),
    name=names,
)
def test_a_reference_survives_its_own_json(
    tmp_path_factory: pytest.TempPathFactory,
    coordinates: list[tuple[float, float]],
    ux: float,
    uy: float,
    name: str,
) -> None:
    from dobladillo.calibration.reference import Feature, ReferenceGeometry, load

    try:
        reference = ReferenceGeometry(
            name=name,
            features=tuple(Feature(f"f{i}", x, y) for i, (x, y) in enumerate(coordinates)),
            relative_uncertainty=(ux, uy),
            status="nominal",
            provenance="generated by a property test",
        )
    except ValueError:
        return  # collinear or otherwise refused: refusing is allowed, round-tripping is not
    path = tmp_path_factory.mktemp("ref") / "reference.json"
    reference.save(path)
    assert load(path) == reference


bases = st.text("ACGT", min_size=1, max_size=40)


@FAST
@given(core=bases, mod=st.sampled_from(["", "/3Bio/", "/5Biosg/", "/36-FAM/"]))
def test_an_order_sequence_with_a_known_modification_is_accepted(core: str, mod: str) -> None:
    from dobladillo.lab.plates import sequence_problem

    assert sequence_problem(core + mod) is None


@FAST
@given(core=bases, bad=st.characters(blacklist_characters="ACGTacgt/", min_codepoint=33))
def test_an_order_sequence_with_any_other_character_is_refused(core: str, bad: str) -> None:
    from dobladillo.lab.plates import sequence_problem

    assert sequence_problem(core + bad) is not None


# ------------------------------------------------------------ settling


@FAST
@given(
    scale=st.floats(0.01, 100.0),
    shift=st.floats(-1e3, 1e3),
    seed=st.integers(0, 2**16),
    trend=st.floats(-5.0, 5.0),
)
def test_the_settling_verdict_does_not_depend_on_units(
    scale: float, shift: float, seed: int, trend: float
) -> None:
    """Whether a series is still moving is the same in nm or in Å, from any zero."""
    from dobladillo.analysis.observables import settling

    rng = np.random.default_rng(seed)
    series = trend * np.linspace(0, 1, 200) + rng.normal(size=200)
    a, b = settling(series), settling(scale * series + shift)
    assert a is not None and b is not None
    assert a.drifting == b.drifting
    assert b.t == pytest.approx(a.t, rel=1e-6)

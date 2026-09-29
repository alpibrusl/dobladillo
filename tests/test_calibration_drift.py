"""Drift against a series whose motion was put in by hand.

The frames are samples of one analytic surface -- smooth bumps of the size of
origami features -- taken at coordinates moved by a known velocity times the
frame time, so every sub-pixel shift is exact rather than interpolated. Then
noise. The drift code must recover the velocity within its own stated
uncertainty, and must not invent one when there is none.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from dobladillo.calibration.drift import drift, register
from dobladillo.imaging.heightmap import HeightMap

PIXEL_NM = 2.0


def field(
    size: int, dx_nm: float, dy_nm: float, *, noise: float = 0.0, seed: int = 0
) -> np.ndarray:
    """One frame of a fixed field of bumps, with the sample moved by (dx, dy)."""
    rng = np.random.default_rng(1)  # the sample: the same in every frame
    extent = size * PIXEL_NM
    count = 80
    cx = rng.uniform(-0.2 * extent, 1.2 * extent, count)
    cy = rng.uniform(-0.2 * extent, 1.2 * extent, count)
    width = rng.uniform(5, 20, count)
    height = rng.uniform(1, 3, count)
    y, x = np.mgrid[0:size, 0:size] * PIXEL_NM
    frame = np.zeros((size, size))
    for i in range(count):
        frame += height[i] * np.exp(
            -((x - dx_nm - cx[i]) ** 2 + (y - dy_nm - cy[i]) ** 2) / (2 * width[i] ** 2)
        )
    return frame + np.random.default_rng(seed).normal(0, noise, frame.shape)


@pytest.mark.parametrize("shift_px", [(0.0, 0.0), (0.37, -1.62), (-6.41, 10.7), (15.06, -25.1)])
def test_register_finds_a_sub_pixel_shift(shift_px: tuple[float, float]) -> None:
    """Noise-free, to the refinement step (0.01 px), up to a fifth of the frame."""
    reference = field(128, 0.0, 0.0)
    moved = field(128, shift_px[1] * PIXEL_NM, shift_px[0] * PIXEL_NM)
    found = register(reference, moved)
    assert found[0] == pytest.approx(shift_px[0], abs=0.02)
    assert found[1] == pytest.approx(shift_px[1], abs=0.02)


@pytest.mark.parametrize("velocity", [(0.3, -0.2), (0.05, 0.12), (-0.45, 0.0)])
def test_drift_recovers_an_imposed_linear_drift(velocity: tuple[float, float]) -> None:
    """20 frames 10 s apart, 0.1 nm noise: each velocity component within
    three of its standard errors, and every frame's displacement within a
    tenth of a pixel of the truth."""
    vx, vy = velocity
    times = np.arange(20) * 10.0
    frames = [
        HeightMap(field(128, vx * t, vy * t, noise=0.1, seed=k + 1), PIXEL_NM)
        for k, t in enumerate(times)
    ]
    result = drift(frames, times)
    assert abs(result.vx_nm_s - vx) <= 3 * result.vx_uncertainty_nm_s
    assert abs(result.vy_nm_s - vy) <= 3 * result.vy_uncertainty_nm_s
    assert np.allclose(result.dx_nm, vx * times, atol=0.1 * PIXEL_NM)
    assert np.allclose(result.dy_nm, vy * times, atol=0.1 * PIXEL_NM)
    assert result.speed_nm_s == pytest.approx(np.hypot(vx, vy), abs=0.01)
    json.dumps(result.as_dict())


def test_no_drift_is_found_where_there_is_none() -> None:
    times = np.arange(10) * 5.0
    frames = [field(96, 0.0, 0.0, noise=0.2, seed=k) for k in range(10)]
    result = drift(frames, times, pixel_nm=PIXEL_NM)
    assert abs(result.vx_nm_s) <= 3 * result.vx_uncertainty_nm_s
    assert abs(result.vy_nm_s) <= 3 * result.vy_uncertainty_nm_s
    assert result.residual_rms_nm < 0.1 * PIXEL_NM


def test_a_drift_that_is_not_linear_shows_in_the_uncertainty() -> None:
    """An accelerating drift is not one velocity, and the error says so: the
    residuals, and with them the slope's standard error, grow far beyond the
    registration noise of a constant drift."""
    times = np.arange(12) * 10.0
    steady = drift(
        [field(96, 0.2 * t, 0.0, noise=0.1, seed=k) for k, t in enumerate(times)],
        times,
        pixel_nm=PIXEL_NM,
    )
    speeding = drift(
        [field(96, 0.002 * t**2, 0.0, noise=0.1, seed=k) for k, t in enumerate(times)],
        times,
        pixel_nm=PIXEL_NM,
    )
    assert speeding.vx_uncertainty_nm_s > 10 * steady.vx_uncertainty_nm_s
    assert speeding.residual_rms_nm > 10 * steady.residual_rms_nm


def test_drift_refuses_what_it_cannot_measure() -> None:
    frame = field(64, 0.0, 0.0)
    with pytest.raises(ValueError, match="at least 3 frames"):
        drift([frame, frame], [0.0, 1.0], pixel_nm=1.0)
    with pytest.raises(ValueError, match="pixel_nm"):
        drift([frame, frame, frame], [0.0, 1.0, 2.0])
    with pytest.raises(ValueError, match="disagrees"):
        drift([HeightMap(frame, 2.0)] * 3, [0.0, 1.0, 2.0], pixel_nm=1.0)
    with pytest.raises(ValueError, match="times"):
        drift([frame] * 3, [0.0, 1.0], pixel_nm=1.0)

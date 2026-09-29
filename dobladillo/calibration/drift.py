"""Drift: how fast the sample moves under the tip, from a series of frames.

A scan takes seconds to minutes, and the sample does not hold still for it:
thermal expansion of the scanner and stage moves it by nanometres per
minute. Within one frame that shears the image along the slow axis (what
`imaging.synthetic`'s `drift_shear` models); between frames of a series --
a high-speed AFM movie, or the same field scanned twice -- it moves every
feature. The second is the one that can be measured directly, and its rate
predicts the first.

**Method.** Each frame is registered against the first by cross-correlation
in Fourier space: the cross-power spectrum of two images that differ by a
shift carries the shift as a phase ramp, and its inverse transform peaks at
the shift. The peak is found on the pixel grid, then refined by evaluating
the same inverse transform on a grid 1/`upsample` of a pixel fine around
it, by matrix multiplication rather than by padding -- the method of
M. Guizar-Sicairos, S. T. Thurman and J. R. Fienup, "Efficient subpixel
image registration algorithms", Opt. Lett. 33, 156 (2008), implemented here
from the paper with numpy's FFT. scikit-image has the same method, but it is
only in the `imaging` extra, and this module should work without it.

The spectrum is used as it is, not normalised to unit magnitude as "phase
correlation" proper does. Normalising weights every frequency equally, and
at the high frequencies of an AFM frame there is nothing but pixel noise: on
the synthetic series in the tests it turned a 0.05 nm scatter of the
displacements about the fitted line into 3 nm.

Each frame is levelled and multiplied by a Hann window before
transforming. Without the window, the image's own edges -- which do not
move with the sample -- dominate the correlation and pull every shift
towards zero. But a window fixed to the frame pulls too, a little (9% of
the shift on those series), because it weights the two frames' content
differently. So the registration is repeated with both windows cut down to
the content the two frames share, each placed where its frame shows it,
until the shift stops moving; then the windowed frames are shifted copies
of each other and the bias goes (a noise-free 25 px shift is found to
0.01 px). A shift beyond about a quarter of the frame leaves too little
shared content for the first pass, whose windows assume no shift, to find
the right peak, and is not supported.

**Reference and uncertainty.** Every frame is registered against the first,
not against its predecessor: chaining consecutive registrations adds their
errors up as a random walk, while a common reference keeps them independent,
which is what the regression below assumes. The drift velocity is the
least-squares slope of displacement against time on each axis, and its
uncertainty the slope's standard error from the residuals. That error
contains both the registration noise and any departure from a constant
velocity, which is the honest thing for it to contain: a drift that is not
linear is not described by one velocity, and the error says so.

**Sign.** `dx_nm`, `dy_nm` are how far the sample content moved in the
image since the first frame, along the fast axis (columns) and slow axis
(rows): frame i shows at (row, col) what frame 0 showed at
(row - dy, col - dx), with dx and dy in pixels.

**What is missing.** Real high-speed movies cannot be loaded yet:
`imaging.readers` refuses `.asd` and `.h5-jpk` stacks (`NOT_READ`), because
the rest of the pipeline measures single images. So this takes a sequence
of `HeightMap`s and the frame times, from wherever they came.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: Sub-pixel refinement factor: shifts are found to 1/UPSAMPLE of a pixel.
#: Chosen well below the registration noise of a real frame, so the grid is
#: never what limits the answer.
UPSAMPLE: Final = 100

#: At most this many registrations per frame pair, each with the windows
#: placed over the content the previous one found shared; it stops as soon
#: as the shift moves by less than the refinement step. Chosen: on the
#: synthetic series in the tests a 25 px shift settles in five.
WINDOW_PASSES: Final = 10

#: Frames needed for a slope with a standard error: two for the line, one
#: more for a residual.
MIN_FRAMES: Final = 3


def _hann(n: int, start: float, length: float) -> np.ndarray:
    """A Hann window over samples start .. start + length of n (zero outside)."""
    x = np.arange(n) - start
    window: np.ndarray = 0.5 - 0.5 * np.cos(2 * np.pi * x / length)
    window[(x < 0) | (x > length)] = 0.0
    return window


def _windows(shape: tuple[int, int], shift: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Hann windows for the reference and the moving frame, over shared content.

    On each axis the content both frames show spans n - 1 - |s| samples;
    the reference's window covers it where the reference shows it, and the
    moving frame's the same content where it has moved to. Both lie wholly
    inside their frames, so the two windowed images are shifted copies of
    each other and the window adds no pull of its own.
    """
    ref_axes, mov_axes = [], []
    for n, s in zip(shape, shift, strict=True):
        length = max(n - 1 - abs(s), 1.0)
        start = max(0.0, -s)
        ref_axes.append(_hann(n, start, length))
        mov_axes.append(_hann(n, start + s, length))
    return np.outer(*ref_axes), np.outer(*mov_axes)


def _upsampled(spectrum: np.ndarray, rows_at: np.ndarray, cols_at: np.ndarray) -> np.ndarray:
    """The inverse DFT of `spectrum` at arbitrary (sub-pixel) positions.

    out[i, j] = sum_k spectrum[k] exp(2 pi i (k_r rows_at[i] / R + k_c cols_at[j] / C)),
    with the frequencies k in numpy's order, negative half included, so the
    result interpolates the pixel-grid inverse transform smoothly.
    """
    rows, cols = spectrum.shape
    k_r = np.fft.fftfreq(rows) * rows
    k_c = np.fft.fftfreq(cols) * cols
    left = np.exp(2j * np.pi * np.outer(rows_at, k_r) / rows)
    right = np.exp(2j * np.pi * np.outer(k_c, cols_at) / cols)
    out: np.ndarray = left @ spectrum @ right
    return out


def _level(frame: np.ndarray, window: np.ndarray) -> np.ndarray:
    """The frame less its mean UNDER THE WINDOW, then windowed.

    The whole-frame mean will not do: the two frames' means differ, because
    they show different content at their edges, and the difference, times
    the window, correlates with the content and pulls the peak (by 1-2% of
    the shift on the series in the tests). The windowed mean is taken over
    the content both windows cover, so it is the same for both.
    """
    mean = float((frame * window).sum() / window.sum())
    levelled: np.ndarray = (frame - mean) * window
    return levelled


def _correlate(
    ref: np.ndarray, mov: np.ndarray, guess: tuple[float, float], upsample: int
) -> tuple[float, float]:
    """One registration, with the windows placed for a shift of `guess`."""
    ref_window, mov_window = _windows(ref.shape, guess)
    spectrum = np.fft.fft2(_level(mov, mov_window)) * np.conj(np.fft.fft2(_level(ref, ref_window)))
    surface = np.abs(np.fft.ifft2(spectrum))
    rows, cols = ref.shape
    peak_r, peak_c = np.unravel_index(int(np.argmax(surface)), surface.shape)
    shift_r = float(peak_r - rows if peak_r > rows // 2 else peak_r)
    shift_c = float(peak_c - cols if peak_c > cols // 2 else peak_c)
    if upsample == 1:
        return shift_r, shift_c
    # 1.5 pixels either side of the coarse peak, at 1/upsample of a pixel.
    steps = np.arange(-1.5 * upsample, 1.5 * upsample + 1) / upsample
    fine = np.abs(_upsampled(spectrum, shift_r + steps, shift_c + steps))
    fine_r, fine_c = np.unravel_index(int(np.argmax(fine)), fine.shape)
    return shift_r + float(steps[fine_r]), shift_c + float(steps[fine_c])


def register(
    reference: np.ndarray, moving: np.ndarray, *, upsample: int = UPSAMPLE
) -> tuple[float, float]:
    """The shift (rows, cols), in pixels, that carries `reference` onto `moving`.

    `moving(p)` is approximately `reference(p - shift)`. Shifts beyond half
    the frame alias to the other side, and a shift that is a large fraction
    of the frame leaves little shared content to register on; neither can be
    fixed by any method that compares whole frames.
    """
    ref = np.asarray(reference, dtype=float)
    mov = np.asarray(moving, dtype=float)
    if ref.shape != mov.shape or ref.ndim != 2:
        raise ValueError(f"frames must be 2D and the same shape, got {ref.shape} and {mov.shape}")
    if upsample < 1:
        raise ValueError(f"upsample must be at least 1, got {upsample}")
    shift = _correlate(ref, mov, (0.0, 0.0), upsample)
    for _ in range(WINDOW_PASSES - 1):
        again = _correlate(ref, mov, shift, upsample)
        moved = max(abs(again[0] - shift[0]), abs(again[1] - shift[1]))
        shift = again
        if moved < 1.0 / upsample:
            break
    return shift


def _slope(times: np.ndarray, values: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Least-squares slope, its standard error, and the residuals."""
    t = times - times.mean()
    sxx = float(t @ t)
    slope = float(t @ (values - values.mean())) / sxx
    residual = values - values.mean() - slope * t
    dof = len(times) - 2
    se = math.sqrt(float(residual @ residual) / dof / sxx)
    return slope, se, residual


@dataclass(frozen=True)
class Drift:
    """Displacement per frame and the constant velocity that best explains it."""

    times_s: tuple[float, ...]
    dx_nm: tuple[float, ...]
    dy_nm: tuple[float, ...]
    vx_nm_s: float
    vy_nm_s: float
    vx_uncertainty_nm_s: float
    vy_uncertainty_nm_s: float
    residual_rms_nm: float
    pixel_nm: float

    @property
    def speed_nm_s(self) -> float:
        return math.hypot(self.vx_nm_s, self.vy_nm_s)

    @property
    def speed_uncertainty_nm_s(self) -> float:
        """First-order propagation; not meaningful for a speed near zero."""
        speed = self.speed_nm_s
        if speed == 0:
            return math.hypot(self.vx_uncertainty_nm_s, self.vy_uncertainty_nm_s)
        return (
            math.hypot(
                self.vx_nm_s * self.vx_uncertainty_nm_s, self.vy_nm_s * self.vy_uncertainty_nm_s
            )
            / speed
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "frames": len(self.times_s),
            "pixel_nm": self.pixel_nm,
            "times_s": [round(t, 4) for t in self.times_s],
            "dx_nm": [round(v, 3) for v in self.dx_nm],
            "dy_nm": [round(v, 3) for v in self.dy_nm],
            "velocity_nm_s": {
                "x": round(self.vx_nm_s, 5),
                "y": round(self.vy_nm_s, 5),
                "x_uncertainty": round(self.vx_uncertainty_nm_s, 5),
                "y_uncertainty": round(self.vy_uncertainty_nm_s, 5),
                "speed": round(self.speed_nm_s, 5),
                "speed_uncertainty": round(self.speed_uncertainty_nm_s, 5),
            },
            "residual_rms_nm": round(self.residual_rms_nm, 4),
            "convention": (
                "content moved by (dx, dy) since the first frame; x = columns (fast axis), "
                "y = rows (slow axis)"
            ),
        }


def drift(
    frames: Sequence[HeightMap] | Sequence[np.ndarray],
    times_s: Sequence[float],
    *,
    pixel_nm: float | None = None,
    upsample: int = UPSAMPLE,
) -> Drift:
    """Drift over a series of frames of the same field, with its uncertainty.

    `frames` are `HeightMap`s, which carry their pixel size, or plain arrays
    with `pixel_nm` given. `times_s` is when each frame was taken -- its
    start or its middle, as long as it is the same for all of them. Frames
    should be flattened alike; a tilt that changes between frames is not a
    shift and will bias one.
    """
    if len(frames) != len(times_s):
        raise ValueError(f"{len(frames)} frames but {len(times_s)} times")
    if len(frames) < MIN_FRAMES:
        raise ValueError(f"need at least {MIN_FRAMES} frames for a velocity with an uncertainty")
    arrays: list[np.ndarray] = []
    sizes: set[float] = set()
    for frame in frames:
        if isinstance(frame, HeightMap):
            arrays.append(frame.heights_nm)
            sizes.add(frame.pixel_nm)
        else:
            arrays.append(np.asarray(frame, dtype=float))
    if pixel_nm is None:
        if len(sizes) != 1 or len(arrays) != sum(isinstance(f, HeightMap) for f in frames):
            raise ValueError("give pixel_nm, or pass HeightMaps that share one pixel size")
        pixel_nm = sizes.pop()
    elif sizes and sizes != {pixel_nm}:
        raise ValueError(f"pixel_nm={pixel_nm} disagrees with the frames' own {sorted(sizes)}")
    if pixel_nm <= 0:
        raise ValueError(f"pixel size must be positive, got {pixel_nm}")
    times = np.asarray(times_s, dtype=float)
    if float(np.ptp(times)) <= 0:
        raise ValueError("frame times must not all be equal")

    shifts = np.array([register(arrays[0], a, upsample=upsample) for a in arrays])
    dy = shifts[:, 0] * pixel_nm
    dx = shifts[:, 1] * pixel_nm
    vx, se_x, res_x = _slope(times, dx)
    vy, se_y, res_y = _slope(times, dy)
    residual = math.sqrt(float(np.mean(res_x**2 + res_y**2)))
    return Drift(
        times_s=tuple(float(t) for t in times),
        dx_nm=tuple(float(v) for v in dx),
        dy_nm=tuple(float(v) for v in dy),
        vx_nm_s=vx,
        vy_nm_s=vy,
        vx_uncertainty_nm_s=se_x,
        vy_uncertainty_nm_s=se_y,
        residual_rms_nm=residual,
        pixel_nm=pixel_nm,
    )

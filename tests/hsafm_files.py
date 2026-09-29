"""Synthetic high-speed AFM movies, written in the byte layout AFMReader parses.

There is no real `.asd` or `.h5-jpk` file in this repository, and AFMReader
0.0.7's wheel ships none of its test files. So these writers produce the
layout that AFMReader's OWN readers consume, field by field, written from
its source (`AFMReader/asd.py`: `read_header_file_version_1`/`_2` and
`read_channel_data`; `AFMReader/h5_jpk.py`: `_available_channels`,
`load_h5jpk`), not from any format document.

What a test on these proves: that `read_stack` hands on what AFMReader
decodes, with the checks and the times this project adds, and that drift is
recovered through the whole path. What it cannot prove: that AFMReader, or
this layout, matches a file written by a real instrument. A file whose layout
AFMReader misreads would be misread here in exactly the same way. That needs
a real movie with a known frame rate and scan size, which is still owed.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

#: The bipolar 2.5 V analogue-digital range code, as AFMReader's
#: `create_analogue_digital_converter` decodes it: height = (R - 2 level R /
#: 4096) x scale. Only that formula is used below, inverted.
BIPOLAR_2_5V = 0x00020000
ADC_RANGE_V = 2.5
ADC_LEVELS = 4096

#: Chosen exactly representable in float32, so the scale AFMReader computes
#: from the header is exactly the one used to quantise here.
Z_PIEZO_GAIN = 2.0
Z_PIEZO_EXTENSION = 5.0  # nm/V; TP scale = gain x extension = 10 nm/V
SCANNER_SENSITIVITY = 4.0  # ER scale = -4


def _levels(heights_nm: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """int16 levels for the heights, and the heights those levels decode to."""
    levels = np.rint((ADC_RANGE_V - heights_nm / scale) * ADC_LEVELS / (2 * ADC_RANGE_V))
    levels = levels.astype(np.int16)
    decoded = (ADC_RANGE_V - 2 * levels.astype(float) * ADC_RANGE_V / ADC_LEVELS) * scale
    return levels, decoded


def write_asd(
    path: Path,
    topography_nm: np.ndarray,
    *,
    x_nm: int,
    y_nm: int,
    frame_time: float = 100.0,
    version: int = 1,
    error_signal: np.ndarray | None = None,
    bits: int = 12,
    initial_frames: int | None = None,
    scan_direction: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Write an .asd with channels TP and ER; return what each decodes to.

    `topography_nm` is (frames, rows, cols); rows are y, the slow axis, as
    AFMReader reshapes them. Heights are quantised to 4096 levels, so the
    returned arrays, not the inputs, are what a reader must give back.
    """
    frames, rows, cols = topography_nm.shape
    error = np.zeros_like(topography_nm) if error_signal is None else error_signal
    tp_levels, tp = _levels(topography_nm, Z_PIEZO_GAIN * Z_PIEZO_EXTENSION)
    er_levels, er = _levels(error, -SCANNER_SENSITIVITY)

    user, comment = b"t\x00e\x00s\x00t\x00", b"synthetic\x00"
    i32 = struct.Struct("<i").pack
    f32 = struct.Struct("<f").pack
    body = b"".join(
        [
            i32(0),  # header_length, filled in below
            i32(32),  # frame_header_length
            i32(0),  # text_encoding
            i32(len(user)),
            i32(len(comment)),
            "TP".encode("utf-16-le"),
            "ER".encode("utf-16-le"),
            i32(frames if initial_frames is None else initial_frames),
            i32(frames),
            i32(scan_direction),
            i32(1),  # file_id
            i32(cols),
            i32(rows),
            i32(x_nm),
            i32(y_nm),
            b"\x00",  # is_averaged
            i32(1),  # averaging_window
            *(i32(v) for v in (2026, 9, 29, 12, 0, 0)),
            i32(0),
            i32(0),  # x, y rounding degree
            f32(frame_time),
            f32(SCANNER_SENSITIVITY),
            f32(1.0),  # phase_sensitivity
            i32(0),  # offset
            b"\x00" * 12,
            i32(0),  # afm_id
            struct.pack("<I", BIPOLAR_2_5V),
            i32(bits),
            f32(float(x_nm)),
            f32(float(y_nm)),
            f32(1.0),
            f32(1.0),  # x, y piezo extension
            f32(Z_PIEZO_EXTENSION),
            f32(Z_PIEZO_GAIN),
            user,
            comment,
        ]
    )
    if version == 2:
        body += b"".join(
            [
                i32(frames),
                i32(0),
                struct.pack("<d", 0.0),  # feed forward
                i32(0),
                i32(0),  # colour scale max, min
                i32(0),
                i32(0),
                i32(0),  # red, green, blue anchor counts
            ]
        )
    elif version != 1:
        raise ValueError("only versions 1 and 2 are written")
    header = i32(version) + i32(4 + len(body)) + body[4:]

    def channel(levels: np.ndarray) -> bytes:
        out = []
        for k in range(frames):
            frame_header = struct.pack("<ihhhhffbbhii", k, 0, 0, 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0)
            assert len(frame_header) == 32
            out.append(frame_header + levels[k].astype("<i2").tobytes())
        return b"".join(out)

    path.write_bytes(header + channel(tp_levels) + channel(er_levels))
    return tp, er


def write_h5jpk(
    path: Path,
    frames_nm: np.ndarray,
    *,
    pixel_nm: float,
    line_rate_hz: float | None,
    slow_pixel_nm: float | None = None,
    slow_pixels: int | None = None,
    multiplier: float = 2.0,
    offset: float = 1e-9,
) -> None:
    """Write an .h5-jpk with one `height` trace channel, as AFMReader reads it.

    AFMReader 0.0.7 takes column k of the channel's dataset as frame k,
    reshapes it square, flips it upside down, applies the channel's scaling
    and converts metres to nanometres; this does the inverse, with a
    non-trivial scaling so it is exercised. A `height` retrace channel is
    added too, so a channel list has more than one entry.
    """
    import h5py

    count, n, n2 = frames_nm.shape
    assert n == n2, "AFMReader's layout is square"
    stored = np.stack([np.flipud(f).ravel() * 1e-9 for f in frames_nm], axis=1)
    stored = (stored - offset) / multiplier
    with h5py.File(path, "w") as f:
        measurement = f.create_group("Measurement_000")
        measurement.attrs["position-pattern.grid.ulength"] = n * pixel_nm * 1e-9
        measurement.attrs["position-pattern.grid.ilength"] = n
        measurement.attrs["position-pattern.grid.vlength"] = (
            (slow_pixels or n) * (slow_pixel_nm or pixel_nm) * 1e-9
        )
        measurement.attrs["position-pattern.grid.jlength"] = slow_pixels or n
        if line_rate_hz is not None:
            measurement.attrs["timing-settings.scanRate"] = line_rate_hz
        for key, retrace in (("Channel_000", False), ("Channel_001", True)):
            channel = measurement.create_group(key)
            channel.attrs["channel.name"] = "height"
            channel.attrs["retrace"] = "true" if retrace else "false"
            channel.attrs["net-encoder.scaling.multiplier"] = multiplier
            channel.attrs["net-encoder.scaling.offset"] = offset
            channel.create_dataset("Height", data=stored if not retrace else -stored)


def drifting_field(
    count: int,
    *,
    size: int = 128,
    pixel_nm: float = 2.0,
    step_nm: tuple[float, float],
    seed: int = 1,
) -> np.ndarray:
    """`count` frames of one field of blobs, moved by `step_nm` (x, y) per frame."""
    rng = np.random.default_rng(seed)
    blobs = 80
    cx, cy = rng.uniform(-50, size * pixel_nm + 50, (2, blobs))
    width, height = rng.uniform(5, 20, blobs), rng.uniform(1, 3, blobs)
    y, x = np.mgrid[0:size, 0:size] * pixel_nm
    frames = []
    for k in range(count):
        dx, dy = step_nm[0] * k, step_nm[1] * k
        frame = sum(
            height[i]
            * np.exp(-((x - dx - cx[i]) ** 2 + (y - dy - cy[i]) ** 2) / (2 * width[i] ** 2))
            for i in range(blobs)
        )
        frames.append(frame + np.random.default_rng(seed * 100 + k).normal(0, 0.05, frame.shape))
    return np.array(frames)

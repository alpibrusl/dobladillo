"""High-speed AFM movies as stacks of frames with their times (`read_stack`).

The movies here are synthetic, written by `hsafm_files` in the layout
AFMReader's own readers parse (see that module). So these tests prove
round-trip consistency with AFMReader's parser and the checks this project
adds on top of it; they do not prove that a file from a real instrument is
read correctly. No real .asd or .h5-jpk is available to this repository.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from hsafm_files import drifting_field, write_asd, write_h5jpk

from dobladillo.imaging.readers import (
    ASD_ADC_BITS,
    UnreadableScan,
    read,
    read_stack,
)

pytest.importorskip("AFMReader")


def _movie(count: int = 4, rows: int = 24, cols: int = 32) -> np.ndarray:
    rng = np.random.default_rng(5)
    return rng.uniform(0.0, 4.0, (count, rows, cols))


@pytest.mark.parametrize("version", [1, 2])
def test_an_asd_movie_comes_back_frame_by_frame_with_its_times(
    tmp_path: Path, version: int
) -> None:
    """Non-square in pixels (24 rows x 32 columns) so a transposed frame fails."""
    heights = _movie()
    expected, _ = write_asd(
        tmp_path / "m.asd",
        heights,
        x_nm=64,
        y_nm=48,
        frame_time=250.0,
        version=version,
        scan_direction=3,
    )
    stack = read_stack(tmp_path / "m.asd")
    assert len(stack.frames) == 4
    assert stack.frames[0].shape == (24, 32)
    assert stack.pixel_nm == 2.0
    for frame, truth, imposed in zip(stack.frames, expected, heights, strict=True):
        np.testing.assert_allclose(frame.heights_nm, truth, atol=1e-9)
        # and within half a quantisation step (2 x 2.5 V / 4096 x 10 nm/V) of what was imposed
        assert np.abs(frame.heights_nm - imposed).max() <= 0.5 * 5.0 / 4096 * 10 + 1e-9
    assert stack.times_s == pytest.approx((0.0, 0.25, 0.5, 0.75))
    assert stack.times_source == "file"
    assert stack.file_interval_s == pytest.approx(0.25)
    assert "milliseconds" in stack.times_note
    assert stack.channel == "TP"
    assert stack.source == "m.asd:TP"
    assert stack.scan_direction == 3


def test_the_second_asd_channel_is_read_by_name_and_a_missing_one_is_listed(
    tmp_path: Path,
) -> None:
    heights = _movie()
    error = np.random.default_rng(9).uniform(-1, 1, heights.shape)
    _, expected_error = write_asd(tmp_path / "m.asd", heights, x_nm=64, y_nm=48, error_signal=error)
    stack = read_stack(tmp_path / "m.asd", channel="ER")
    np.testing.assert_allclose(stack.frames[2].heights_nm, expected_error[2], atol=1e-9)
    with pytest.raises(UnreadableScan) as caught:
        read_stack(tmp_path / "m.asd", channel="PH")
    assert "TP" in str(caught.value) and "ER" in str(caught.value)


def test_an_asd_without_a_frame_time_is_refused_not_given_one(tmp_path: Path) -> None:
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=48, frame_time=0.0)
    with pytest.raises(UnreadableScan, match="--interval-s") as caught:
        read_stack(tmp_path / "m.asd")
    assert "no usable frame time" in str(caught.value)
    # the caller's times stand in, and the stack says whose they are
    stack = read_stack(tmp_path / "m.asd", interval_s=0.5)
    assert stack.times_s == pytest.approx((0.0, 0.5, 1.0, 1.5))
    assert stack.times_source == "given"
    assert stack.file_interval_s is None


def test_an_asd_frame_time_that_cannot_be_milliseconds_is_refused(tmp_path: Path) -> None:
    """0.2 read as ms is 0.2 ms a frame: a frame time stored in seconds, most likely."""
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=48, frame_time=0.2)
    with pytest.raises(UnreadableScan, match="unit is more likely wrong"):
        read_stack(tmp_path / "m.asd")


def test_an_asd_with_frames_removed_is_refused_unless_times_are_given(tmp_path: Path) -> None:
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=48, initial_frames=10)
    with pytest.raises(UnreadableScan, match="frames were removed"):
        read_stack(tmp_path / "m.asd")
    stack = read_stack(tmp_path / "m.asd", times_s=[0.0, 0.1, 0.7, 0.9])
    assert stack.times_s == (0.0, 0.1, 0.7, 0.9)
    with pytest.raises(ValueError, match="4 frames but 3 times"):
        read_stack(tmp_path / "m.asd", times_s=[0.0, 0.1, 0.7])


def test_an_asd_of_another_bit_depth_is_refused(tmp_path: Path) -> None:
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=48, bits=14)
    with pytest.raises(UnreadableScan, match=r"2\*\*\(14 - 12\)"):
        read_stack(tmp_path / "m.asd")


def test_afmreader_ignores_the_asd_bit_depth_which_is_why_it_is_checked(tmp_path: Path) -> None:
    """A conformance test on the dependency, like the .top one in test_readers.

    AFMReader 0.0.7 decodes a 14-bit file exactly as a 12-bit one, and
    computes the header's resolution as `2 ^ bits` (XOR). When this fails,
    AFMReader has started using the bit depth: re-check ASD_ADC_BITS."""
    from AFMReader.asd import load_asd

    write_asd(tmp_path / "a.asd", _movie(), x_nm=64, y_nm=48, bits=ASD_ADC_BITS)
    write_asd(tmp_path / "b.asd", _movie(), x_nm=64, y_nm=48, bits=14)
    frames_12, _, header_12 = load_asd(tmp_path / "a.asd", "TP")
    frames_14, _, header_14 = load_asd(tmp_path / "b.asd", "TP")
    np.testing.assert_array_equal(frames_12, frames_14)
    assert header_12["analogue_digital_resolution"] == 12 ^ 2 == 14
    assert header_14["analogue_digital_data_bits_size"] == 14


def test_non_square_asd_pixels_are_refused(tmp_path: Path) -> None:
    """AFMReader logs a warning and returns the x pitch; this refuses."""
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=60)
    with pytest.raises(UnreadableScan, match="square"):
        read_stack(tmp_path / "m.asd")


def test_a_damaged_asd_is_refused_not_a_traceback(tmp_path: Path) -> None:
    path = tmp_path / "m.asd"
    path.write_bytes(b"\x01\x00\x00\x00" + b"\xff" * 40)
    with pytest.raises(UnreadableScan, match="AFMReader could not read"):
        read_stack(path)


def test_an_h5jpk_movie_comes_back_with_afmreaders_nominal_times(tmp_path: Path) -> None:
    heights = _movie(count=3, rows=16, cols=16)
    write_h5jpk(tmp_path / "m.h5-jpk", heights, pixel_nm=2.5, line_rate_hz=64.0)
    stack = read_stack(tmp_path / "m.h5-jpk")
    assert stack.pixel_nm == pytest.approx(2.5)
    for frame, truth in zip(stack.frames, heights, strict=True):
        np.testing.assert_allclose(frame.heights_nm, truth, atol=1e-9)
    # 16 lines a frame at 64 lines/s
    assert stack.times_s == pytest.approx((0.0, 0.25, 0.5))
    assert stack.file_interval_s == pytest.approx(0.25)
    assert stack.times_source == "file"
    assert stack.channel == "height_trace"
    assert "nominal" in stack.times_note
    retrace = read_stack(tmp_path / "m.h5-jpk", channel="height_retrace")
    np.testing.assert_allclose(retrace.frames[0].heights_nm, -heights[0] + 2e-9 * 1e9, atol=1e-9)


def test_h5jpk_refusals(tmp_path: Path) -> None:
    heights = _movie(count=3, rows=16, cols=16)
    cases = {
        "rect.h5-jpk": ({"slow_pixel_nm": 3.0}, "square"),
        "shape.h5-jpk": ({"slow_pixels": 12}, "16 x 12"),
        "norate.h5-jpk": ({"line_rate_hz": None}, "scanRate"),
    }
    for name, (overrides, message) in cases.items():
        kwargs: dict = {"pixel_nm": 2.5, "line_rate_hz": 64.0, **overrides}
        write_h5jpk(tmp_path / name, heights, **kwargs)
        with pytest.raises(UnreadableScan, match=message):
            read_stack(tmp_path / name)
    with pytest.raises(UnreadableScan, match="height_trace"):
        read_stack(tmp_path / "rect.h5-jpk", channel="amplitude_trace")
    (tmp_path / "junk.h5-jpk").write_bytes(b"not hdf5")
    with pytest.raises(UnreadableScan, match="HDF5"):
        read_stack(tmp_path / "junk.h5-jpk")


def test_the_missing_line_rate_cannot_be_replaced_by_given_times(tmp_path: Path) -> None:
    """AFMReader 0.0.7 computes the times inside its loader and fails without
    the line rate, so no frames come back at all; saying --interval-s would
    help would be false."""
    write_h5jpk(tmp_path / "m.h5-jpk", _movie(3, 16, 16), pixel_nm=2.5, line_rate_hz=None)
    with pytest.raises(UnreadableScan, match="cannot stand in"):
        read_stack(tmp_path / "m.h5-jpk", interval_s=1.0)


def test_single_image_readers_refuse_a_movie_and_say_where_it_is_read(tmp_path: Path) -> None:
    write_asd(tmp_path / "m.asd", _movie(), x_nm=64, y_nm=48)
    with pytest.raises(UnreadableScan, match="calibrate drift"):
        read(tmp_path / "m.asd")


def test_read_stack_refuses_a_single_image_file(tmp_path: Path) -> None:
    from dobladillo.imaging.heightmap import HeightMap
    from dobladillo.imaging.readers import write_gsf

    path = write_gsf(HeightMap(np.zeros((8, 8)), 1.0), tmp_path / "a.gsf")
    with pytest.raises(UnreadableScan, match="not a movie format"):
        read_stack(path)


def test_a_drift_imposed_on_an_asd_movie_is_recovered_through_read_stack(tmp_path: Path) -> None:
    """Ground truth end to end, in code: 3 and -2 nm/s at 0.5 s a frame."""
    from dobladillo.calibration.drift import drift

    heights = drifting_field(10, step_nm=(1.5, -1.0))
    write_asd(tmp_path / "m.asd", heights, x_nm=256, y_nm=256, frame_time=500.0)
    stack = read_stack(tmp_path / "m.asd")
    result = drift(stack.frames, stack.times_s)
    assert abs(result.vx_nm_s - 3.0) <= max(3 * result.vx_uncertainty_nm_s, 0.02)
    assert abs(result.vy_nm_s + 2.0) <= max(3 * result.vy_uncertainty_nm_s, 0.02)

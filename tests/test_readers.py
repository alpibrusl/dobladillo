"""Getting a scan in, and refusing to guess at one we cannot read.

There are no instrument files to test against -- `alpibrupa/nanoindent` ships
none -- which is most of the argument for reading Gwyddion Simple Field rather
than writing a parser per vendor. GSF can be tested exactly, by writing files
and reading them back, and Gwyddion exports it from every native format.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dobladillo.imaging.classify import population
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.readers import (
    EXPORT_INSTRUCTION,
    GSF_MAGIC,
    READERS,
    UnreadableScan,
    read,
    read_gsf,
    write_gsf,
)
from dobladillo.imaging.synthetic import synthetic_scan


def _image(rows: int = 32, cols: int = 32, pixel_nm: float = 2.0) -> HeightMap:
    rng = np.random.default_rng(11)
    return HeightMap(
        heights_nm=rng.normal(3.0, 0.4, (rows, cols)), pixel_nm=pixel_nm, source="made up"
    )


def test_gsf_round_trips(tmp_path: Path) -> None:
    original = _image()
    back = read(write_gsf(original, tmp_path / "s.gsf"))
    assert back.shape == original.shape
    assert back.pixel_nm == pytest.approx(original.pixel_nm)
    # float32 on the wire, so exactness is not available and is not wanted.
    assert np.abs(back.heights_nm - original.heights_nm).max() < 1e-5


def test_a_non_square_scan_round_trips_with_its_axes_the_right_way_round(tmp_path: Path) -> None:
    """Rows and columns are the classic place to transpose something and not
    notice, because a square test image cannot tell you."""
    original = _image(rows=16, cols=48)
    back = read(write_gsf(original, tmp_path / "s.gsf"))
    assert back.shape == (16, 48)
    assert np.abs(back.heights_nm - original.heights_nm).max() < 1e-5


def test_metres_are_converted_to_nanometres(tmp_path: Path) -> None:
    """GSF is in metres and this project is in nanometres throughout. A missed
    factor of 1e9 would make every particle a billionth of its size, which is
    at least obvious; a missed factor on ONE axis would not be."""
    path = tmp_path / "s.gsf"
    write_gsf(HeightMap(heights_nm=np.full((4, 4), 2.0), pixel_nm=1.5), path)
    raw = path.read_bytes()
    assert b"XReal = 6e-09" in raw or b"XReal = 5.9999" in raw or b"XReal = 6.0000" in raw
    back = read_gsf(path)
    assert back.pixel_nm == pytest.approx(1.5)
    assert back.heights_nm.max() == pytest.approx(2.0, abs=1e-5)


def _header(**fields: object) -> bytes:
    text = "".join(f"{k} = {v}\n" for k, v in fields.items()).encode()
    blob = GSF_MAGIC + text
    return blob + b"\x00" * (4 - len(blob) % 4 or 4)


def test_a_file_that_is_not_gsf_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "s.gsf"
    path.write_bytes(b"not a gsf at all")
    with pytest.raises(UnreadableScan, match="wrong magic"):
        read_gsf(path)


def test_a_truncated_file_is_refused_rather_than_padded(tmp_path: Path) -> None:
    path = tmp_path / "s.gsf"
    path.write_bytes(_header(XRes=8, YRes=8) + b"\x00" * 16)
    with pytest.raises(UnreadableScan, match="truncated"):
        read_gsf(path)


def test_rectangular_pixels_are_refused(tmp_path: Path) -> None:
    """Not wrong, but everything downstream assumes one pixel size, and taking
    the mean of two would put a few per cent into every reported dimension
    without saying so anywhere."""
    path = tmp_path / "s.gsf"
    path.write_bytes(
        _header(XRes=8, YRes=8, XReal=1e-6, YReal=2e-6, XYUnits="m", ZUnits="m")
        + np.zeros(64, dtype="<f4").tobytes()
    )
    with pytest.raises(UnreadableScan, match="square pixels"):
        read_gsf(path)


@pytest.mark.parametrize("field", ["XYUnits", "ZUnits"])
def test_unexpected_units_are_refused(tmp_path: Path, field: str) -> None:
    path = tmp_path / "s.gsf"
    units = {"XYUnits": "m", "ZUnits": "m", field: "furlong"}
    path.write_bytes(
        _header(XRes=4, YRes=4, XReal=1e-6, YReal=1e-6, **units)
        + np.zeros(16, dtype="<f4").tobytes()
    )
    with pytest.raises(UnreadableScan, match="unsupported"):
        read_gsf(path)


def test_an_unknown_format_says_what_to_do_instead(tmp_path: Path) -> None:
    """The error is the documentation. A partner sent a .spm and needs to know
    the next step, not that a suffix was not in a dictionary."""
    path = tmp_path / "scan.spm"
    path.write_text("whatever")
    with pytest.raises(UnreadableScan) as caught:
        read(path)
    assert "Gwyddion" in str(caught.value)
    assert EXPORT_INSTRUCTION in str(caught.value)


def test_a_missing_file_is_not_a_format_problem(tmp_path: Path) -> None:
    with pytest.raises(UnreadableScan, match="no such file"):
        read(tmp_path / "absent.gsf")


def test_a_browser_saved_jpk_keeps_its_real_suffix(tmp_path: Path) -> None:
    """JPK files arrive as .jpk-force-map.zip often enough that dispatching on
    the last suffix alone would reject a file we can actually read."""
    assert ".jpk-force-map" in READERS
    path = tmp_path / "x.jpk-force-map.zip"
    path.write_bytes(b"not really a zip")
    with pytest.raises(UnreadableScan) as caught:
        read(path)
    assert "not a format this reads" not in str(caught.value)


def test_a_synthetic_scan_survives_the_whole_path(tmp_path: Path) -> None:
    """The point of the module. Ground truth we chose, written out as the file
    format a partner would send, read back through the reader, and measured --
    so a fault anywhere in that chain shows up as a wrong count rather than as
    a plausible one."""
    from dobladillo.compare.corrections import half_height_broadening_nm

    scan = synthetic_scan(seed=7)
    image = read(write_gsf(scan.image, tmp_path / "s.gsf"))
    flattened, background = flatten(image)
    # The fixture renders a finite tip, so the image shows the object widened
    # by it. Judging the image against the object's own dimensions would fail
    # here for a reason that has nothing to do with reading the file.
    broadening = 2 * half_height_broadening_nm(tip_radius_nm=10.0, feature_height_nm=2.0)
    found = population(
        find_particles(flattened, background),
        length_nm=191.0 + broadening,
        width_nm=36.0 + broadening,
        height_nm=2.0,
    )
    assert found.counts.get("well_formed", 0) == len(scan.rectangles)
    assert found.counts.get("malformed", 0) == 0


def test_a_scan_that_starts_at_exactly_zero_is_read_correctly(tmp_path: Path) -> None:
    """The regression. The header's NUL padding was found by scanning forward
    while the byte was NUL, which walks into the data whenever the first
    height serialises with a leading zero byte -- any flat region at exactly
    0.0. A random test image cannot catch it; this one is all zeros."""
    original = HeightMap(heights_nm=np.zeros((8, 8)), pixel_nm=1.0)
    back = read(write_gsf(original, tmp_path / "flat.gsf"))
    assert back.shape == (8, 8)
    assert np.array_equal(back.heights_nm, np.zeros((8, 8)))


def test_a_scan_whose_first_value_is_zero_keeps_the_rest(tmp_path: Path) -> None:
    heights = np.arange(64, dtype=float).reshape(8, 8)  # first value is 0.0
    back = read(write_gsf(HeightMap(heights_nm=heights, pixel_nm=1.0), tmp_path / "s.gsf"))
    assert np.abs(back.heights_nm - heights).max() < 1e-5

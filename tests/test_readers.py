"""Getting a scan in, and refusing to guess at one we cannot read.

Two kinds of file. GSF is tested exactly, by writing files and reading them
back. Native instrument files are read through AFMReader and tested against
real vendor files from AFMReader's own test suite (`tests/data/afm_native/`,
with their source and licence), with pixel sizes checked against the values
AFMReader's tests state. They are not partner files; that fixture is still
owed.
"""

from __future__ import annotations

import re
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
    """The error is the documentation. A partner sent a Park .tiff and needs to
    know the next step, not that a suffix was not in a dictionary."""
    path = tmp_path / "scan.nid"
    path.write_text("whatever")
    with pytest.raises(UnreadableScan) as caught:
        read(path)
    assert "Gwyddion" in str(caught.value)
    assert EXPORT_INSTRUCTION in str(caught.value)


def test_a_truncated_bruker_file_is_refused_rather_than_hanging(tmp_path: Path) -> None:
    """Found by the first version of the test below, which never finished.

    pySPM reads a Bruker header line by line until `\\*File list end` and has
    no end-of-file check, so a truncated .spm -- or any file that is not one --
    spins forever. A partner's half-copied file would hang `experiment report`
    with no message at all. The adapter checks for the line first."""
    pytest.importorskip("AFMReader")
    path = tmp_path / "scan.spm"
    path.write_text("whatever")
    with pytest.raises(UnreadableScan, match="no complete Bruker header"):
        read(path)


def test_a_damaged_native_file_is_refused_not_a_traceback(tmp_path: Path) -> None:
    """A .spm used to be refused by suffix. Now it is read, so a broken one
    must fail as an unreadable scan -- the CLI's contract -- whatever exception
    the vendor parser happens to trip on. This one has a header that ends and
    says nothing."""
    pytest.importorskip("AFMReader")
    path = tmp_path / "scan.001"
    path.write_bytes(b"\\*File list\r\n\\*File list end\r\n")
    with pytest.raises(UnreadableScan, match="AFMReader could not read"):
        read(path)


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


# ------------------------------------------------------ native, via AFMReader

NATIVE_FIXTURES = Path(__file__).resolve().parent / "data" / "afm_native"


@pytest.mark.parametrize(
    ("name", "pixel_nm", "shape", "image_sum"),
    [
        # Every number here is copied from AFMReader's own tests
        # (tests/test_jpk.py, tests/test_stp.py at v0.0.7), not measured here.
        ("sample_0.jpk", 1.2770176335964876, (256, 256), 219242202.8256843),
        ("sample_0.jpk-qi-image", 4.999999999999986, (100, 100), 31593146.16051172),
        ("sample_0.stp", 0.9765625, (512, 512), -15070620.440757688),
    ],
)
def test_a_native_file_is_read_with_the_pixel_size_its_reader_states(
    name: str, pixel_nm: float, shape: tuple[int, int], image_sum: float
) -> None:
    """The acceptance test for reading native formats. The image sum is the
    check that heights come through unaltered and in nanometres: a factor of
    1e9 missed or applied twice moves it by nine orders of magnitude."""
    pytest.importorskip("AFMReader")
    image = read(NATIVE_FIXTURES / name)
    assert image.pixel_nm == pytest.approx(pixel_nm, rel=1e-9)
    assert image.shape == shape
    assert float(image.heights_nm.sum()) == pytest.approx(image_sum, rel=1e-9)


def test_the_wsxm_pixel_size_agrees_with_the_header_not_just_with_afmreader() -> None:
    """An independent check on one of them: the .stp header states the scan
    size in plain text, so the pitch can be computed without AFMReader."""
    pytest.importorskip("AFMReader")
    path = NATIVE_FIXTURES / "sample_0.stp"
    header = path.read_bytes()[:6000].decode("latin-1")
    size = float(re.search(r"X Amplitude: ([\d.]+) nm", header).group(1))  # type: ignore[union-attr]
    columns = int(re.search(r"Number of columns: (\d+)", header).group(1))  # type: ignore[union-attr]
    assert read(path).pixel_nm == pytest.approx(size / columns)


def test_the_channel_is_recorded_in_the_source() -> None:
    """Which channel a number came from is part of what it means."""
    pytest.importorskip("AFMReader")
    assert read(NATIVE_FIXTURES / "sample_0.jpk").source == "sample_0.jpk:height_trace"


def test_a_missing_channel_lists_the_ones_there_are_and_takes_none_of_them() -> None:
    """No fallback to a nearby channel: an amplitude or error signal read as a
    height would be measured happily and mean nothing."""
    pytest.importorskip("AFMReader")
    with pytest.raises(UnreadableScan) as caught:
        read(NATIVE_FIXTURES / "sample_0.jpk", channel="topography")
    assert "height_trace" in str(caught.value)


def test_another_channel_can_be_asked_for_by_name() -> None:
    pytest.importorskip("AFMReader")
    trace = read(NATIVE_FIXTURES / "sample_0.jpk")
    retrace = read(NATIVE_FIXTURES / "sample_0.jpk", channel="height_retrace")
    assert retrace.source.endswith("height_retrace")
    assert not np.array_equal(trace.heights_nm, retrace.heights_nm)


def test_a_single_image_format_refuses_a_channel() -> None:
    pytest.importorskip("AFMReader")
    with pytest.raises(UnreadableScan, match="holds one image"):
        read(NATIVE_FIXTURES / "sample_0.stp", channel="Height")


def test_non_square_jpk_pixels_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """AFMReader keeps the fast-axis pitch and drops the slow one. The adapter
    reads both, and refuses a mismatch exactly as the GSF reader does. There
    is no non-square JPK file to test with, so the second pitch is replaced;
    the real file passing above is the negative control."""
    pytest.importorskip("AFMReader")
    from dobladillo.imaging import readers

    monkeypatch.setattr(readers, "_jpk_pitches_nm", lambda path: (1.277, 1.4))
    with pytest.raises(UnreadableScan, match="square pixels"):
        read(NATIVE_FIXTURES / "sample_0.jpk")


def test_afmreader_truncates_top_heights_which_is_why_top_is_refused() -> None:
    """A conformance test on the dependency, and it currently fails it.

    `sample_0.top` and `sample_0.stp` are the same acquisition, saved twice by
    WSXM. The .stp's height range is the header's Z amplitude, 59.7449 nm. The
    .top comes back spanning 59.0: AFMReader 0.0.7 matches `Z Amplitude:
    (\\d+)` and so keeps only the integer part. For a 4.53 nm scan that is 12%
    off every height, enough to move a twisted sheet across the 1.25x
    boundary.

    When this test fails, AFMReader has fixed it: check, then let .top in.
    """
    pytest.importorskip("AFMReader")
    from AFMReader.stp import load_stp
    from AFMReader.top import load_top

    stp, _ = load_stp(NATIVE_FIXTURES / "sample_0.stp")
    top, _ = load_top(NATIVE_FIXTURES / "sample_0.top")
    same_shape = (top - top.min()) / np.ptp(top) - (stp - stp.min()) / np.ptp(stp)
    assert np.abs(same_shape).max() < 1e-9, "not the same acquisition after all"
    assert np.ptp(stp) == pytest.approx(59.7449)
    assert np.ptp(top) == pytest.approx(59.0), "AFMReader's .top heights changed: re-check"

    with pytest.raises(UnreadableScan, match="integer part"):
        read(NATIVE_FIXTURES / "sample_0.top")


@pytest.mark.parametrize("suffix", [".asd", ".h5-jpk"])
def test_a_high_speed_stack_is_refused_with_the_reason(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"movie{suffix}"
    path.write_bytes(b"\x00" * 16)
    with pytest.raises(UnreadableScan, match="frames"):
        read(path)


def test_bruker_numbered_files_are_read_as_spm() -> None:
    """Nanoscope names files scan.001, scan.002. Renaming a raw file is
    forbidden in during/raw, so the reader has to accept the name it has."""
    from dobladillo.imaging.readers import is_native_image, suffix_of

    assert suffix_of(Path("scan.001")) == ".spm"
    assert suffix_of(Path("scan.SPM")) == ".spm"
    assert suffix_of(Path("x.jpk-force-map.zip")) == ".jpk-force-map"
    assert is_native_image(Path("scan.017"))
    # Negative controls: an export, a force map and a number that is not
    # three digits are not native images.
    assert not is_native_image(Path("scan.gsf"))
    assert not is_native_image(Path("x.jpk-force-map"))
    assert not is_native_image(Path("scan.01"))


def test_without_afmreader_a_native_file_says_how_to_get_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The imaging module is meant to work on its own; a missing optional
    dependency is an instruction, not an ImportError."""
    import importlib

    from dobladillo.imaging import readers

    real = importlib.import_module

    def without_afmreader(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("AFMReader"):
            raise ImportError(f"No module named {name!r}")
        return real(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(readers.importlib, "import_module", without_afmreader)
    path = tmp_path / "scan.jpk"
    path.write_bytes(b"\x00" * 16)
    with pytest.raises(UnreadableScan) as caught:
        read(path)
    assert "uv sync --extra imaging" in str(caught.value)
    assert ".gsf" in str(caught.value)


#: AFMReader's larger fixtures, not copied into this repository: Bruker .spm is
#: 32 MB. Pointed at by AFMREADER_RESOURCES when a checkout is at hand.
LARGE = [
    # name, channel, pixel size, shape, image sum -- from AFMReader's tests.
    ("sample_0.spm", "Height", 0.4940029296875, (1024, 1024), 30695369.188316286),
    ("sample_0.ibw", "HeightTracee", 1.5625, (512, 512), -218091520.0),
    ("sample_0.gwy", "ZSensor", 0.8468632812499975, (512, 512), 33836850.232917726),
]


@pytest.mark.parametrize(("name", "channel", "pixel_nm", "shape", "image_sum"), LARGE)
def test_the_large_native_formats_when_a_checkout_is_available(
    name: str, channel: str, pixel_nm: float, shape: tuple[int, int], image_sum: float
) -> None:
    import os

    pytest.importorskip("AFMReader")
    resources = os.environ.get("AFMREADER_RESOURCES")
    if not resources or not (Path(resources) / name).is_file():
        pytest.skip("set AFMREADER_RESOURCES to an AFMReader checkout's tests/resources")
    image = read(Path(resources) / name, channel=channel)
    assert image.pixel_nm == pytest.approx(pixel_nm, rel=1e-9)
    assert image.shape == shape
    # .ibw arrives as float32 and is summed here in float64, so not to 1e-9.
    assert float(image.heights_nm.sum()) == pytest.approx(image_sum, rel=1e-6)


def test_afm_read_opens_a_native_file() -> None:
    """The issue's acceptance criterion, through the command a person runs."""
    pytest.importorskip("AFMReader")
    import json

    from typer.testing import CliRunner

    from dobladillo.cli import app

    result = CliRunner().invoke(
        app, ["afm", "read", str(NATIVE_FIXTURES / "sample_0.jpk"), "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["pixel_nm"] == pytest.approx(1.277, abs=1e-3)
    assert payload["pixels"] == {"rows": 256, "cols": 256}
    assert payload["source"] == "sample_0.jpk:height_trace"
    assert payload["square_pixels_checked"] is True


def test_afm_read_says_when_square_pixels_are_assumed(tmp_path: Path) -> None:
    """Bruker, Asylum and Gwyddion files give one pitch; `afm read` says the
    other was not checked instead of letting silence imply it was. Tested on
    the dispatch rather than a 32 MB file: `SINGLE_PITCH` is what the command
    reads."""
    from dobladillo.imaging.readers import SINGLE_PITCH, suffix_of

    assert {".spm", ".ibw", ".gwy"} <= SINGLE_PITCH
    assert suffix_of(Path("scan.002")) in SINGLE_PITCH
    assert ".jpk" not in SINGLE_PITCH and ".gsf" not in SINGLE_PITCH

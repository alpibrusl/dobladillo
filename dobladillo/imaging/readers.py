"""Getting a real scan into a `HeightMap`, without writing a parser per vendor.

**Native instrument files are read directly, through AFMReader.** This module
used to say they could not be, and asked every partner to export Gwyddion
Simple Field first. That was wrong: AFMReader (AFM-SPM, University of
Sheffield -- the file layer under TopoStats) reads Bruker `.spm`, JPK `.jpk`,
Asylum `.ibw`, Gwyddion `.gwy`, WSXM and high-speed `.asd`, and returns the
image with its pixel-to-nanometre scale. It is maintained, and it is tested
against real instrument files in its own repository, which is the one thing a
reader written here never could be.

The adapter is thin on purpose, and strict where AFMReader is permissive:

- **One height channel per format by default**, named in `NATIVE`, and never a
  fallback to a different one. A channel that is not there is an error that
  lists the ones that are; picking "the nearest" would read an amplitude or an
  error signal as a height and nothing downstream could tell.
- **Square pixels are checked where the file says both pitches.** AFMReader
  returns one scale, taken from one axis. For JPK the second axis is read here
  from the same TIFF tags AFMReader uses, and a mismatch is refused, as it is
  for GSF. For `.spm`, `.ibw` and `.gwy` there is no second number to compare
  against without writing the parser this module exists not to write; see
  `SINGLE_PITCH`.
- **Formats whose heights are known to be wrong are refused**, with the reason.
  AFMReader 0.0.7 rescales WSXM `.top` heights to the *integer part* of the
  header's Z amplitude -- 4.53 nm becomes 4 -- found by reading the `.stp` of the
  same acquisition next to it. See `NOT_READ`.

GSF stays. `afm synthetic` writes it, it is fully specified, the reader for it
is tested exactly by writing files and reading them back, and it is still the
way in for an instrument AFMReader does not cover (Park, Nanosurf): export from
Gwyddion. Native force maps are still read through pyfmreader when it is
installed.

AFMReader is GPL-3.0 (its `COPYING`; its PyPI classifier says LGPLv3, its
`CITATION.cff` GPL-3.0-or-later, and the most restrictive of the three is the
one recorded). That is compatible with EUPL-1.2 and costs nothing while this
runs internally. It matters the day anything that bundles it is distributed.
It is an optional dependency, in the `imaging` extra, imported only when a
native file is read, so the GSF path works without it.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: Gwyddion Simple Field's first line, exactly. The format is a text header,
#: NUL padding to a four byte boundary, then XRes*YRes little-endian float32 in
#: row-major order. http://gwyddion.net/documentation/user-guide-en/gsf.html
GSF_MAGIC: Final = b"Gwyddion Simple Field 1.0\n"

#: GSF stores lengths in metres unless XYUnits says otherwise, and this project
#: works in nanometres everywhere.
M_TO_NM: Final = 1e9

EXPORT_INSTRUCTION: Final = """\
Bruker .spm (and .001-style), JPK .jpk, Asylum .ibw, Gwyddion .gwy and WSXM .stp
are read directly. For anything else, open the file in Gwyddion, choose the
height channel, and use File > Save As with the .gsf extension (Gwyddion Simple
Field). Gwyddion reads the formats this does not -- Park, Nanosurf and others --
and .gsf is fully specified rather than reverse engineered from samples."""

INSTALL_INSTRUCTION: Final = """\
Reading native instrument files needs AFMReader, in the `imaging` extra:
    uv sync --extra imaging        (or: pip install 'dobladillo[imaging]')
Without it, export the height channel as .gsf from Gwyddion instead."""


class UnreadableScan(ValueError):
    """A file this module will not guess at."""


def _parse_gsf_header(blob: bytes) -> tuple[dict[str, str], int]:
    """Header fields, and where the binary data starts."""
    if not blob.startswith(GSF_MAGIC):
        raise UnreadableScan("not a Gwyddion Simple Field file: wrong magic line")
    end = blob.find(b"\x00", len(GSF_MAGIC))
    if end < 0:
        raise UnreadableScan("truncated .gsf: the header has no NUL terminator")
    fields = {}
    for line in blob[len(GSF_MAGIC) : end].decode("utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    # The spec pads the header with one to four NULs so the binary data starts
    # at a multiple of four. Computing that from `end` is the only correct way
    # to find it: scanning forward while the byte is NUL walks straight into
    # the data whenever the first height serialises with a leading zero byte,
    # which any flat region at exactly 0.0 does.
    start = end + (4 - end % 4 if end % 4 else 4)
    if blob[end:start] != b"\x00" * (start - end):
        raise UnreadableScan("malformed .gsf: the header padding is not all NUL")
    return fields, start


def read_gsf(path: Path) -> HeightMap:
    """Read a Gwyddion Simple Field file.

    Only square pixels are accepted. A scan with different X and Y pitch is not
    wrong, but every measurement downstream assumes one pixel size, and
    silently taking the mean of two would put a few per cent into every
    reported dimension without saying so.
    """
    blob = path.read_bytes()
    fields, start = _parse_gsf_header(blob)
    try:
        cols, rows = int(fields["XRes"]), int(fields["YRes"])
    except (KeyError, ValueError) as exc:
        raise UnreadableScan("a .gsf must give integer XRes and YRes") from exc
    if cols <= 0 or rows <= 0:
        raise UnreadableScan(f"a scan cannot be {cols} by {rows}")

    expected = rows * cols * 4
    data = blob[start : start + expected]
    if len(data) != expected:
        raise UnreadableScan(
            f"truncated .gsf: {rows}x{cols} needs {expected} bytes of data, found {len(data)}"
        )
    heights = np.frombuffer(data, dtype="<f4").reshape(rows, cols).astype(float)

    # XReal/YReal are the scan's physical size; both default to 1.0 in the spec.
    x_real = float(fields.get("XReal", 1.0))
    y_real = float(fields.get("YReal", 1.0))
    units = fields.get("XYUnits", "m")
    scale = M_TO_NM if units == "m" else 1.0
    if units not in {"m", "nm"}:
        raise UnreadableScan(f"unsupported XYUnits {units!r}; expected m or nm")
    pixel_x = x_real * scale / cols
    pixel_y = y_real * scale / rows
    if not np.isclose(pixel_x, pixel_y, rtol=1e-6):
        raise UnreadableScan(
            f"pixels are {pixel_x:.4f} by {pixel_y:.4f} nm; this pipeline assumes square "
            "pixels and would put the difference into every reported dimension"
        )

    z_units = fields.get("ZUnits", "m")
    if z_units == "m":
        heights = heights * M_TO_NM
    elif z_units != "nm":
        raise UnreadableScan(f"unsupported ZUnits {z_units!r}; expected m or nm")

    return HeightMap(
        heights_nm=heights,
        pixel_nm=pixel_x,
        source=fields.get("Title") or path.name,
    )


def write_gsf(image: HeightMap, path: Path, *, title: str = "") -> Path:
    """Write a `HeightMap` as GSF.

    Here so the reader can be tested against files this module did not itself
    interpret, and because handing an AFM partner a synthetic scan of known
    contents is the cheapest way to check their end of the pipeline before any
    real sample is imaged.
    """
    rows, cols = image.shape
    header = (
        GSF_MAGIC
        + (
            f"XRes = {cols}\n"
            f"YRes = {rows}\n"
            f"XReal = {cols * image.pixel_nm / M_TO_NM!r}\n"
            f"YReal = {rows * image.pixel_nm / M_TO_NM!r}\n"
            "XYUnits = m\n"
            "ZUnits = m\n"
            f"Title = {title or image.source}\n"
        ).encode()
    )
    padding = b"\x00" * (4 - len(header) % 4 or 4)
    body = (image.heights_nm / M_TO_NM).astype("<f4").tobytes()
    path.write_bytes(header + padding + body)
    return path


def read_jpk_force_map(path: Path, *, channel: str = "height") -> HeightMap:
    """The topography recorded alongside a JPK force map or QI scan.

    Through `alpibrupa/nanoindent`'s vendored pyfmreader, which is a byte for
    byte snapshot of a reader whose output appears in published tables. It
    handles `jpk-force-map` and `jpk-qi-data` only; a plain topography scan is
    not one of those, and there is no path to it here.
    """
    try:
        from nanoindent.dynamo_v0.pyfmreader.jpk.loadjpkimg import loadJPKimg
        from nanoindent.dynamo_v0.pyfmreader.pyfmreader import loadfile
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise UnreadableScan(
            "reading JPK force maps needs alpibrupa/nanoindent installed.\n\n" + EXPORT_INSTRUCTION
        ) from exc

    uff = loadfile(str(path))
    channels = loadJPKimg(uff) or {}
    if not channels:
        raise UnreadableScan(
            f"{path.name} carries no image channels pyfmreader recognises. If it is a "
            "plain topography scan rather than a force map, that reader does not "
            "cover it.\n\n" + EXPORT_INSTRUCTION
        )
    matched = next((k for k in channels if channel.lower() in k.lower()), None)
    if matched is None:
        raise UnreadableScan(f"no channel matching {channel!r}; this file has {sorted(channels)}")

    heights = np.asarray(channels[matched], dtype=float) * M_TO_NM
    metadata = getattr(uff, "filemetadata", {})
    scan_m = metadata.get("scan_size_x") or metadata.get("force_map_scan_size_x")
    if not scan_m:
        raise UnreadableScan(
            f"{path.name} does not declare a scan size, so its pixel pitch is unknown "
            "and every dimension measured from it would be arbitrary.\n\n" + EXPORT_INSTRUCTION
        )
    pixel_nm = float(scan_m) * M_TO_NM / heights.shape[1]
    return HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source=f"{path.name}:{matched}")


@dataclass(frozen=True)
class NativeFormat:
    """One native format, as AFMReader reads it."""

    #: The AFMReader submodule and its loader function.
    module: str
    loader: str
    #: The channel read when none is asked for, taken from AFMReader's own
    #: docstrings and tests. None for a format that holds one image.
    channel: str | None
    instrument: str


#: Suffix to native format. The default channel is the topography: the one a
#: person would have picked in Gwyddion before exporting. Anything else has to
#: be asked for by name.
NATIVE: Final = {
    ".spm": NativeFormat("spm", "load_spm", "Height", "Bruker Nanoscope"),
    ".jpk": NativeFormat("jpk", "load_jpk", "height_trace", "JPK NanoWizard"),
    ".jpk-qi-image": NativeFormat("jpk", "load_jpk", "height_trace", "JPK QI image"),
    # "HeightTracee" is not a typo: it is the label Asylum's software writes,
    # and AFMReader's docstring says so.
    ".ibw": NativeFormat("ibw", "load_ibw", "HeightTracee", "Asylum Research (Igor)"),
    ".gwy": NativeFormat("gwy", "load_gwy", "Height", "Gwyddion native"),
    ".stp": NativeFormat("stp", "load_stp", None, "WSXM"),
}

#: Bruker writes `scan.001`, `scan.002`, ... as often as `.spm`. pySPM, which
#: AFMReader reads them through, goes by content rather than suffix.
BRUKER_NUMBERED: Final = re.compile(r"\.\d{3}")

#: Formats AFMReader reports a single pixel pitch for, with no second axis in
#: reach of this adapter. Read, and said so by `afm read`, rather than refused:
#: nearly every scan is square, and refusing all of them to catch the rare one
#: that is not would send people back to the export step for nothing.
SINGLE_PITCH: Final = frozenset({".spm", ".ibw", ".gwy"})

#: Formats AFMReader reads that this deliberately does not, and why.
NOT_READ: Final = {
    ".top": (
        "AFMReader 0.0.7 rescales WSXM .top heights to the integer part of the header's "
        "Z amplitude -- 4.53 nm is read as 4, 59.74 as 59 -- so every height would be up to "
        "12% low. Read the .stp of the same image instead: WSXM saves both, and the .stp "
        "carries the heights themselves."
    ),
    ".asd": (
        "this is a high-speed AFM movie, a stack of frames. This pipeline measures single "
        "images; export the frame to measure as .gsf from Gwyddion."
    ),
    ".h5-jpk": (
        "this is a JPK high-speed stack, a series of frames. This pipeline measures single "
        "images; export the frame to measure as .gsf from Gwyddion."
    ),
}


def _afmreader(module: str) -> Any:
    """Import one AFMReader submodule, or say how to get it.

    AFMReader configures loguru to print every step to stderr at INFO. That
    is right for its own GUI and wrong under a CLI whose --json promises one
    object on stdout and nothing else, so it is silenced here.
    """
    try:
        imported = importlib.import_module(f"AFMReader.{module}")
        from loguru import logger
    except ImportError as exc:
        raise UnreadableScan(INSTALL_INSTRUCTION) from exc
    logger.disable("AFMReader")
    return imported


def _jpk_pitches_nm(path: Path) -> tuple[float, float]:
    """Both pixel pitches of a JPK image, fast axis first.

    AFMReader's own scaling reads the fast axis and discards the slow one.
    This reads both from the same TIFF tags, numbered from AFMReader's own
    configuration file rather than transcribed here, so the two cannot drift.
    """
    from importlib import resources

    import tifffile

    # AFMReader's own YAML reader on AFMReader's own file, exactly as its
    # JPK loader does it.
    config = Path(str(resources.files("AFMReader") / "default_config.yaml"))
    tags = _afmreader("io").read_yaml(config)["jpk"]
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]

        def tag(name: str) -> float:
            return float(page.tags[tags[name]].value)  # type: ignore[union-attr]

        fast = tag("grid_ulength") / tag("grid_ilength") * M_TO_NM
        slow = tag("grid_vlength") / tag("grid_jlength") * M_TO_NM
    return fast, slow


#: Where a Bruker header ends. pySPM reads the header line by line until it
#: sees this and has no end-of-file check, so a file without it -- truncated,
#: or not a Bruker file at all -- makes it loop forever rather than fail.
BRUKER_HEADER_END: Final = b"\\*File list end"

#: How far into a Bruker file to look for that line. Headers are tens of
#: kilobytes; this is generous and still cheap next to the image data.
BRUKER_HEADER_SEARCH_BYTES: Final = 4 * 1024 * 1024


def _check_bruker_header(path: Path) -> None:
    """Refuse a .spm that would hang pySPM, before handing it over."""
    with path.open("rb") as handle:
        head = handle.read(BRUKER_HEADER_SEARCH_BYTES)
    if BRUKER_HEADER_END not in head:
        raise UnreadableScan(
            f"{path.name} has no complete Bruker header (no '\\*File list end'): it is "
            "truncated, or not a Nanoscope file. Copy it from the instrument again."
        )


def read_native(path: Path, *, suffix: str, channel: str | None = None) -> HeightMap:
    """A native instrument file, through AFMReader.

    Heights come back in nanometres for the height channels -- AFMReader
    converts JPK, Asylum and Gwyddion heights from metres, and Bruker's
    through pySPM -- and the pixel scale in nanometres per pixel. Other
    channels (amplitude, phase, error signals) are returned in whatever unit
    the instrument stored, which is one more reason the default is the height
    channel and nothing else.
    """
    fmt = NATIVE[suffix]
    if fmt.channel is None and channel is not None:
        raise UnreadableScan(f"{path.name}: a {suffix} file holds one image; it has no channels")
    wanted = channel or fmt.channel
    loader = getattr(_afmreader(fmt.module), fmt.loader)
    if fmt.module == "spm":
        _check_bruker_header(path)
    try:
        result = loader(path) if wanted is None else loader(path, wanted)
    except FileNotFoundError as exc:
        raise UnreadableScan(f"no such file: {path}") from exc
    except Exception as exc:
        # A damaged or unexpected vendor file fails with whatever the
        # library's parser trips on -- struct errors, KeyErrors, TIFF errors.
        # All of them mean the same thing here, and a traceback helps nobody.
        raise UnreadableScan(
            f"AFMReader could not read {path.name} as {fmt.instrument} {suffix}: {exc}"
        ) from exc
    image, pixel_nm = result[0], result[1]

    heights = np.asarray(image, dtype=float)
    if heights.ndim != 2:
        raise UnreadableScan(
            f"{path.name} gave a {heights.ndim}-dimensional array; this measures single images"
        )
    if pixel_nm is None or not np.isfinite(pixel_nm) or pixel_nm <= 0:
        raise UnreadableScan(
            f"{path.name} does not give a usable pixel size ({pixel_nm!r}), so every "
            "dimension measured from it would be arbitrary"
        )
    if not np.isfinite(heights).all():
        raise UnreadableScan(
            f"{path.name} has {int((~np.isfinite(heights)).sum())} missing or infinite "
            "heights -- an interrupted scan, usually. Crop to the finished part in "
            "Gwyddion and export that as .gsf."
        )
    if fmt.module == "jpk":
        fast, slow = _jpk_pitches_nm(path)
        if not np.isclose(fast, slow, rtol=1e-6):
            raise UnreadableScan(
                f"pixels are {fast:.4f} by {slow:.4f} nm; this pipeline assumes square "
                "pixels and would put the difference into every reported dimension"
            )
    return HeightMap(
        heights_nm=heights,
        pixel_nm=float(pixel_nm),
        source=f"{path.name}:{wanted}" if wanted else path.name,
    )


#: Suffix to reader, for the formats read here rather than through AFMReader.
READERS: Final = {
    ".gsf": read_gsf,
    ".jpk-force-map": read_jpk_force_map,
    ".jpk-qi-data": read_jpk_force_map,
}


def suffix_of(path: Path) -> str:
    """The suffix that decides the reader, normalised.

    JPK files are often saved as `.jpk-force-map.zip` by the browser, and
    Bruker numbers its files, so neither the last suffix nor a lookup table
    alone is enough.
    """
    suffix = path.suffix.lower()
    if suffix == ".zip" and len(path.suffixes) > 1:
        suffix = path.suffixes[-2].lower()
    if BRUKER_NUMBERED.fullmatch(suffix):
        return ".spm"
    return suffix


def is_native_image(path: Path) -> bool:
    """Whether this is an instrument image file this reads directly."""
    return suffix_of(path) in NATIVE


def read(path: Path, *, channel: str | None = None) -> HeightMap:
    """Read a scan, or say plainly what to do instead.

    `channel` picks a channel in a multi-channel native file; the default is
    the format's height channel, named in `NATIVE`.
    """
    path = Path(path)
    if not path.exists():
        raise UnreadableScan(f"no such file: {path}")
    suffix = suffix_of(path)
    if suffix in NATIVE:
        return read_native(path, suffix=suffix, channel=channel)
    if suffix in NOT_READ:
        raise UnreadableScan(f"{path.name}: {NOT_READ[suffix]}")
    reader = READERS.get(suffix)
    if reader is None:
        readable = sorted({*READERS, *NATIVE, ".001"})
        raise UnreadableScan(
            f"{path.name} is not a format this reads ({', '.join(readable)}).\n\n"
            + EXPORT_INSTRUCTION
        )
    if channel is None:
        return reader(path)
    if suffix == ".gsf":
        raise UnreadableScan(f"{path.name}: a .gsf holds one image; it has no channels")
    return read_jpk_force_map(path, channel=channel)

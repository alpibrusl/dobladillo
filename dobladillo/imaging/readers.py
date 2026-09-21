"""Getting a real scan into a `HeightMap`, without writing a parser per vendor.

The obvious plan was to reuse `alpibrupa/nanoindent`'s instrument readers, and
`docs/STATUS.md` said M4's file formats were solved there. Reading them showed
that is only half true, and the half matters.

`loadJPKimg` accepts `jpk-force-map` and `jpk-qi-data` and returns None for
anything else; `loadNANOSCimg` reads the force-volume image offsets out of a
Nanoscope header. Both extract the topography recorded *alongside a force
volume*. Neither reads a plain tapping-mode topography scan, which is exactly
what an AFM group imaging origami on mica produces. There are also no sample
files in that repository, so a parser written against those formats here could
not be tested against anything.

So the approach is different, and better. **Gwyddion reads every native AFM
format there is, and exports Gwyddion Simple Field.** One reader for GSF covers
every instrument a partner might own, is fully specified, and can be tested
exactly -- by writing files and reading them back -- rather than hopefully. The
cost is one export step for the person sending the data, and the instruction is
one line long.

Native force-map files are still read through pyfmreader when it is installed,
because that path does work and costs nothing to offer. Anything else fails
with the export instruction rather than with a guess.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

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
Open the file in Gwyddion, choose the height channel, and use
File > Save As with the .gsf extension (Gwyddion Simple Field).

Gwyddion reads every native format this project is likely to be sent -- Bruker,
JPK, Asylum, Nanosurf, Park -- so one export covers all of them, and .gsf is a
fully specified format rather than one reverse engineered from samples."""


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


#: Suffix to reader. Deliberately short: the answer to a format not here is to
#: export GSF, not to add a parser nobody can test.
READERS: Final = {
    ".gsf": read_gsf,
    ".jpk-force-map": read_jpk_force_map,
    ".jpk-qi-data": read_jpk_force_map,
}


def read(path: Path) -> HeightMap:
    """Read a scan, or say plainly what to do instead."""
    path = Path(path)
    if not path.exists():
        raise UnreadableScan(f"no such file: {path}")
    suffix = path.suffix.lower()
    # JPK files are often saved as .jpk-force-map.zip by the browser.
    if suffix == ".zip" and len(path.suffixes) > 1:
        suffix = path.suffixes[-2].lower()
    reader = READERS.get(suffix)
    if reader is None:
        raise UnreadableScan(
            f"{path.name} is not a format this reads ({', '.join(sorted(READERS))}).\n\n"
            + EXPORT_INSTRUCTION
        )
    return reader(path)

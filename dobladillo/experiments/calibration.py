"""The K experiments' readout: every calibration a folder's scans support.

`calibrate lateral|tip|drift` take scan files. This finds them in an
experiment folder's `during/raw/` by name, takes the conditions they were
taken under from `during/instrument.json`, and runs whichever of the three
the folder has data for. `calibrate report` writes the result to
`post/calibration.json`: per analysis, the payload the file-level command
gives for the same files, the conditions, and the hashes of the scans used.

**Naming in `during/raw/`.** Taken from what the K protocols already asked
for; where they disagreed, what most of them used.

- **Lateral** reads the reference tile's scans, `pattern-NN.<ext>` (detail,
  K2, K3, K5, K7, K8) and `overlap-NN.<ext>` (K3's overlap size). They may sit
  in `during/raw/` itself or in any subfolder -- `liquid/`, `air/`, `iso/`,
  `K-01/`, `t0/F-20/` -- and a subfolder is an arm: its scans are never
  pooled with another's, and `pattern-` and `overlap-` are never pooled with
  each other (different scan sizes). Scans at different scan angles are
  fitted apart too, since a scale x at 90 degrees is the other piezo's. So
  one calibration per (subfolder, prefix, angle). The protocols' example
  command lines said `tile-*`; no protocol named an image that way.
- **Tip** reads K4's blocks, `<block>-NN.<ext>` where the block is a sample
  letter and a number (`S1-01`, `T2-03`, `B1-01`), in any subfolder
  (`staircase/`, `tile/`, `bundle/`). Each scan is reconstructed on its own
  and listed with its block. K4 is the only protocol that names tip scans.
- **Drift** reads a series of frames, `frame-NN.<ext>`, one series per
  subfolder, frames in number order. The frame times come from the record,
  `frames.interval_s` or `frames.times_s[<subfolder>]`. A high-speed AFM
  movie (`.asd`, `.h5-jpk`, K6) is one series, carrying its own frame times
  (`_movie_series`, through `imaging.readers.read_stack`).

Everything else in `during/raw/` -- gels, gratings, `control-*` -- is not
read. As everywhere (`experiments.pattern.scans_for`), native files are read
in preference to `.gsf` exports of them, never both.

**What each needs from the record, and refuses without** (`REQUIRES`):
lateral, the reference (`calibration_reference`, or the folder's part when it
is `calibration-tile`), the scan angle, direction and loop, and the
deposition cations; tip, the direction and the tip's part number; drift, the
scan angle, the loop and the frame times. Each analysis refuses on its own,
with a `kind`, and the others still run. Nothing is defaulted: a nominal
tile geometry is used only because the folder was made for that part, and a
tile rebuilt today that is not the design the folder predicted is refused.

It does not evaluate the gate, and it does not summarise across arms, codes
or time points (K5's spread, K7's shelf life, K8's budget): those are not
built.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from dobladillo.experiments.arms import RecordIncomplete
from dobladillo.experiments.instrument import (
    CALIBRATION_CONDITIONS,
    ConditionField,
    Conditions,
    angle_for,
    read_conditions,
)

Analysis = Literal["lateral", "tip", "drift"]

ANALYSES: Final[tuple[Analysis, ...]] = ("lateral", "tip", "drift")

#: Name prefixes of the reference's scans, read by the lateral calibration.
LATERAL_PREFIXES: Final = ("pattern", "overlap")

#: Name prefix of a drift series' frames.
FRAME_PREFIX: Final = "frame"

#: K4's tip scans: a block (sample letter, block number) and an index.
TIP_BLOCK: Final = re.compile(r"(?P<block>[A-Z]\d+)-\d+")

#: High-speed AFM movies: one file, many frames, not read yet (issue #26).
MOVIE_SUFFIXES: Final = (".asd", ".h5-jpk")

_FIELDS: Final = {f.name: f for f in CALIBRATION_CONDITIONS}
TIP_PART_FIELD: Final = ConditionField(
    ("tip", "part_number"),
    "the probe the tip belongs to, so a reconstruction can be tied to its tip record",
    "the part number or model, as text",
    "no_tip_part_number",
)

#: What each analysis needs from `during/instrument.json`, beyond the scans.
REQUIRES: Final[dict[Analysis, tuple[str, ...]]] = {
    "lateral": (
        "scan.angle_deg",
        "scan.direction",
        "scan.closed_loop",
        "deposition.mgcl2_mm",
        "deposition.nicl2_mm",
    ),
    "tip": ("scan.direction", "tip.part_number"),
    "drift": ("scan.angle_deg", "scan.closed_loop"),
}

INSTRUMENT: Final = "during/instrument.json"


@dataclass(frozen=True)
class ScanSet:
    """Files one analysis reads together, and the name the report gives them."""

    analysis: Analysis
    name: str
    #: The subfolder under during/raw, "." for during/raw itself.
    folder: str
    files: tuple[Path, ...]
    block: str | None = None


@dataclass(frozen=True)
class Discovery:
    sets: tuple[ScanSet, ...]
    movies: tuple[Path, ...]

    def of(self, analysis: Analysis) -> list[ScanSet]:
        return [s for s in self.sets if s.analysis == analysis]


@dataclass(frozen=True)
class Options:
    bootstrap: int = 200
    size_px: int = 31
    threshold_sigma: float | None = None
    feature_height_nm: float = 2.0


@dataclass
class Refusal:
    kind: str
    message: str
    missing: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "message": self.message}
        if self.missing:
            out["missing"] = list(self.missing)
        return out


# ---------------------------------------------------------------- discovery


def _stem(path: Path) -> str:
    """The name without any suffix: `S1-01.001` and `pattern-01.spm` alike."""
    return path.name.split(".", 1)[0]


def _natural(path: Path) -> list[Any]:
    """Sort key putting frame-2 before frame-10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path.name)]


def _preferred(files: list[Path]) -> list[Path]:
    """Native files, or failing those their .gsf exports; never both."""
    from dobladillo.imaging.readers import is_native_image, suffix_of

    native = [p for p in files if is_native_image(p)]
    return native or [p for p in files if suffix_of(p) == ".gsf"]


def relative(path: Path, directory: Path) -> str:
    """A path as the record names it: under `during/raw/`."""
    return path.relative_to(directory / "during" / "raw").as_posix()


def discover(directory: Path) -> Discovery:
    """Every scan set `during/raw/` holds, by the naming above."""
    from dobladillo.imaging.readers import suffix_of
    from dobladillo.provenance import raw_files

    raw = directory / "during" / "raw"
    groups: dict[tuple[Analysis, str, str], list[Path]] = {}
    movies: list[Path] = []
    for path in raw_files(directory):
        folder = path.parent.relative_to(raw).as_posix()
        stem = _stem(path)
        if suffix_of(path) in MOVIE_SUFFIXES:
            movies.append(path)
            continue
        prefix = stem.split("-", 1)[0]
        if prefix in LATERAL_PREFIXES and stem.startswith(f"{prefix}-"):
            groups.setdefault(("lateral", folder, prefix), []).append(path)
        elif prefix == FRAME_PREFIX and stem.startswith(f"{prefix}-"):
            groups.setdefault(("drift", folder, ""), []).append(path)
        elif TIP_BLOCK.fullmatch(stem):
            groups.setdefault(("tip", folder, stem), []).append(path)

    sets = []
    for (analysis, folder, key), files in sorted(groups.items()):
        chosen = sorted(_preferred(files), key=_natural)
        if not chosen:
            continue
        if analysis == "lateral":
            name = key if folder == "." else f"{folder}/{key}"
            sets.append(ScanSet(analysis, name, folder, tuple(chosen)))
        elif analysis == "drift":
            sets.append(ScanSet(analysis, folder, folder, tuple(chosen)))
        else:
            match = TIP_BLOCK.fullmatch(key)
            block = match.group("block") if match else None
            sets += [
                ScanSet(analysis, relative(p, directory), folder, (p,), block=block) for p in chosen
            ]
    return Discovery(sets=tuple(sets), movies=tuple(sorted(movies)))


# ---------------------------------------------------------------- the record


@dataclass(frozen=True)
class Record:
    """What the analyses read from the folder besides the scans."""

    data: dict[str, Any]
    conditions: Conditions
    instrument_sha256: str
    part: str | None
    #: Where the calibration reference comes from, as recorded.
    reference_spec: str | None
    reference_from: str | None


def read_record(directory: Path) -> Record:
    """The instrument record and the folder's part; refuses only on the file itself."""
    from dobladillo.provenance import file_sha256

    if not directory.is_dir():
        raise RecordIncomplete(f"no experiment folder {directory}", kind="missing_folder")
    path = directory / "during" / "instrument.json"
    if not path.is_file():
        raise RecordIncomplete(
            f"no {INSTRUMENT}: the conditions every calibration depends on are recorded "
            "there, and none is assumed",
            kind="no_instrument",
        )
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        raise RecordIncomplete(
            f"{INSTRUMENT} is not valid JSON: {e}", kind="invalid_reading"
        ) from e
    if not isinstance(data, dict):
        raise RecordIncomplete(f"{INSTRUMENT} is not a JSON object", kind="invalid_reading")

    part = None
    prediction = directory / "pre" / "prediction.json"
    if prediction.is_file():
        try:
            loaded = json.loads(prediction.read_text())
            part = loaded.get("part") if isinstance(loaded, dict) else None
        except ValueError:
            part = None
    explicit = data.get("calibration_reference")
    if isinstance(explicit, str) and explicit.strip():
        spec, source = explicit.strip(), f"{INSTRUMENT}: calibration_reference"
    elif part == "calibration-tile":
        spec, source = "calibration-tile", "pre/prediction.json: part"
    else:
        spec, source = None, None
    return Record(
        data=data,
        conditions=read_conditions(data),
        instrument_sha256=file_sha256(path),
        part=part,
        reference_spec=spec,
        reference_from=source,
    )


def _value(record: Record, name: str) -> Any:
    if name == TIP_PART_FIELD.name:
        value = (record.data.get("tip") or {}).get("part_number")
        return value.strip() or None if isinstance(value, str) else None
    return record.conditions.get(name)


def _missing(record: Record, analysis: Analysis) -> Refusal | None:
    """The first thing `analysis` needs that the record lacks, as a refusal."""
    names = REQUIRES[analysis]
    invalid = [
        why for why in record.conditions.invalid if any(why.startswith(f"{n}:") for n in names)
    ]
    if invalid:
        return Refusal(
            "invalid_reading",
            f"{INSTRUMENT}: " + "; ".join(invalid),
            tuple(why.split(":", 1)[0] for why in invalid),
        )
    absent = [n for n in names if _value(record, n) is None]
    if not absent:
        return None
    fields = [TIP_PART_FIELD if n == TIP_PART_FIELD.name else _FIELDS[n] for n in absent]
    detail = "; ".join(f"{f.name} ({f.allowed})" for f in fields)
    return Refusal(
        fields[0].kind,
        f"{INSTRUMENT} does not record what the {analysis} calibration depends on: {detail}. "
        "Write what was used at the instrument -- not the protocol's value, not a guess.",
        tuple(absent),
    )


def _channel(record: Record, files: tuple[Path, ...]) -> tuple[str | None, Refusal | None]:
    """The channel to read, refusing a retrace analysis that would read the trace."""
    from dobladillo.imaging.readers import NATIVE, suffix_of

    channel = (record.data.get("scan") or {}).get("channel")
    channel = channel.strip() or None if isinstance(channel, str) else None
    multi = [p for p in files if (fmt := NATIVE.get(suffix_of(p))) and fmt.channel is not None]
    if record.conditions.get("scan.direction") == "retrace" and channel is None and multi:
        return None, Refusal(
            "invalid_reading",
            f"{INSTRUMENT} says scan.direction is retrace but names no scan.channel, so "
            f"{multi[0].name} would be read from its format's default height channel "
            f"({NATIVE[suffix_of(multi[0])].channel}; the trace in JPK and Asylum files). "
            "Name the channel the analysis should read, as `dobladillo afm read` lists them.",
            ("scan.channel",),
        )
    return channel, None


def _read(files: tuple[Path, ...], channel: str | None) -> list[Any]:
    """The scans, each with the record's channel where its format has channels."""
    from dobladillo.imaging.readers import NATIVE, UnreadableScan, read, suffix_of

    images = []
    for path in files:
        fmt = NATIVE.get(suffix_of(path))
        takes_channel = fmt is not None and fmt.channel is not None
        try:
            images.append(read(path, channel=channel if takes_channel else None))
        except (UnreadableScan, OSError) as e:
            message = str(e)
            raise UnreadableScan(
                message if path.name in message else f"{path.name}: {message}"
            ) from e
    return images


# ---------------------------------------------------------------- analyses


@dataclass
class Outcome:
    """One analysis over one set: a result, or a refusal, never both."""

    entry: dict[str, Any]
    files: tuple[Path, ...] = ()

    @property
    def refused(self) -> bool:
        return "refused" in self.entry


def _resolve_reference(
    directory: Path, record: Record
) -> tuple[Any, dict[str, Any], Refusal | None]:
    """The reference geometry, how it was chosen and its identity, or a refusal."""
    from dobladillo.calibration import reference as ref
    from dobladillo.provenance import design_sha256, file_sha256, folder_chain, short

    identity: dict[str, Any] = {"spec": record.reference_spec, "from": record.reference_from}
    if record.reference_spec is None:
        return (
            None,
            identity,
            Refusal(
                "no_calibration_reference",
                "nothing records what the scanned reference is: the folder was not made for "
                f"the calibration tile (pre/prediction.json's part is {record.part!r}), and "
                f"{INSTRUMENT} has no calibration_reference. Name 'calibration-tile' or a "
                "reference JSON (path relative to the folder, as `calibrate reference --out` "
                "writes or a certificate gives).",
                ("calibration_reference",),
            ),
        )
    if record.reference_spec == "calibration-tile":
        from dobladillo.parts.calibration_tile import calibration_tile

        tile = calibration_tile()
        built = design_sha256(tile.design)
        identity["design_sha256"] = built
        chain = folder_chain(directory, scans=[])
        for recorded, what in (
            (chain.predicted_design, "pre/prediction.json predicts"),
            (chain.scan_design, "pre/order ordered"),
        ):
            if recorded is not None and recorded != built:
                return (
                    None,
                    identity,
                    Refusal(
                        "design_mismatch",
                        f"{what} design {short(recorded)}, but the calibration tile built "
                        f"today is design {short(built)}: its nominal marks are not the ones "
                        "on this sample. Declare the folded design's geometry as a reference "
                        "JSON and name it in calibration_reference.",
                    ),
                )
        return ref.from_tile(tile), identity, None
    path = directory / record.reference_spec
    if not path.is_file():
        return (
            None,
            identity,
            Refusal(
                "no_calibration_reference",
                f"{INSTRUMENT}'s calibration_reference {record.reference_spec!r} is not a file "
                "in this folder",
                ("calibration_reference",),
            ),
        )
    try:
        geometry = ref.load(path)
    except (ValueError, KeyError, TypeError) as e:
        return (
            None,
            identity,
            Refusal("invalid_reading", f"{record.reference_spec}: not a usable reference: {e}"),
        )
    identity["sha256"] = file_sha256(path)
    return geometry, identity, None


def _lateral(
    directory: Path, record: Record, sets: list[ScanSet], options: Options
) -> tuple[dict[str, Any], list[Outcome]]:
    from dobladillo.calibration.lateral import CalibrationRefused
    from dobladillo.calibration.payloads import lateral_payload
    from dobladillo.imaging.readers import UnreadableScan

    refusal = _missing(record, "lateral")
    geometry: Any = None
    identity: dict[str, Any] = {}
    if refusal is None:
        geometry, identity, refusal = _resolve_reference(directory, record)
    if refusal is None:
        _, refusal = _channel(record, tuple(p for s in sets for p in s.files))
    if refusal is not None or geometry is None:
        assert refusal is not None
        return {"reference": identity or None}, [
            Outcome({"set": s.name, "refused": refusal.as_dict()}) for s in sets
        ]

    angle_record = record.conditions.get("scan.angle_deg")
    channel, _ = _channel(record, tuple(p for s in sets for p in s.files))
    outcomes: list[Outcome] = []
    for scan_set in sets:
        by_angle: dict[float, list[Path]] = {}
        unmatched = []
        for path in scan_set.files:
            angle = angle_for(angle_record, relative(path, directory))
            if angle is None:
                unmatched.append(relative(path, directory))
            else:
                by_angle.setdefault(angle, []).append(path)
        if unmatched:
            outcomes.append(
                Outcome(
                    {
                        "set": scan_set.name,
                        "refused": Refusal(
                            "no_scan_angle",
                            f"{INSTRUMENT}'s scan.angle_deg gives no angle for "
                            f"{', '.join(unmatched)}",
                            ("scan.angle_deg",),
                        ).as_dict(),
                    }
                )
            )
            continue
        for angle, angled in sorted(by_angle.items()):
            files = tuple(angled)
            name = scan_set.name if len(by_angle) == 1 else f"{scan_set.name} @ {angle:g} deg"
            base = {
                "set": name,
                "scans": [relative(p, directory) for p in files],
                "scan_angle_deg": angle,
            }
            try:
                payload, _ = lateral_payload(
                    _read(files, channel), geometry, bootstrap=options.bootstrap
                )
            except (UnreadableScan, OSError) as e:
                outcomes.append(
                    Outcome({**base, "refused": Refusal("unreadable_scan", str(e)).as_dict()})
                )
                continue
            except CalibrationRefused as e:
                outcomes.append(
                    Outcome({**base, "refused": Refusal("calibration_refused", str(e)).as_dict()})
                )
                continue
            payload["scans"] = [str(p) for p in files]
            outcomes.append(Outcome({**base, "result": payload}, files))
    return {"reference": identity}, outcomes


def _tip(
    directory: Path, record: Record, sets: list[ScanSet], options: Options
) -> tuple[dict[str, Any], list[Outcome]]:
    from dobladillo.calibration.payloads import tip_payload
    from dobladillo.calibration.tip import THRESHOLD_SIGMA
    from dobladillo.imaging.readers import UnreadableScan

    settings = {
        "size_px": options.size_px,
        "threshold_sigma": THRESHOLD_SIGMA
        if options.threshold_sigma is None
        else options.threshold_sigma,
        "feature_height_nm": options.feature_height_nm,
    }
    refusal = _missing(record, "tip")
    if refusal is None:
        _, refusal = _channel(record, tuple(p for s in sets for p in s.files))
    if refusal is not None:
        return settings, [Outcome({"scan": s.name, "refused": refusal.as_dict()}) for s in sets]
    channel, _ = _channel(record, tuple(p for s in sets for p in s.files))
    outcomes = []
    for scan_set in sets:
        base = {"scan": scan_set.name, "block": scan_set.block, "folder": scan_set.folder}
        try:
            (image,) = _read(scan_set.files, channel)
            found = tip_payload(
                image,
                source=str(scan_set.files[0]),
                size_px=options.size_px,
                threshold_sigma=options.threshold_sigma,
                feature_height_nm=options.feature_height_nm,
            )
        except (UnreadableScan, OSError) as e:
            outcomes.append(
                Outcome({**base, "refused": Refusal("unreadable_scan", str(e)).as_dict()})
            )
            continue
        except ValueError as e:
            outcomes.append(
                Outcome({**base, "refused": Refusal("invalid_parameters", str(e)).as_dict()})
            )
            continue
        outcomes.append(Outcome({**base, "result": found.payload}, scan_set.files))
    return settings, outcomes


def _frame_times(
    record: Record, scan_set: ScanSet
) -> tuple[list[float] | None, str, Refusal | None]:
    """A series' frame times from the record, and where they came from."""
    frames = record.data.get("frames") or {}
    listed = (frames.get("times_s") or {}) if isinstance(frames, dict) else {}
    interval = frames.get("interval_s") if isinstance(frames, dict) else None
    count = len(scan_set.files)
    if isinstance(listed, dict) and scan_set.folder in listed:
        times = listed[scan_set.folder]
        source = f"{INSTRUMENT}: frames.times_s[{scan_set.folder!r}]"
        if not isinstance(times, list) or not all(
            isinstance(t, int | float) and not isinstance(t, bool) for t in times
        ):
            return None, source, Refusal("invalid_reading", f"{source} is not a list of seconds")
        if len(times) != count:
            return (
                None,
                source,
                Refusal("invalid_reading", f"{source} has {len(times)} times for {count} frames"),
            )
        return [float(t) for t in times], source, None
    if isinstance(interval, int | float) and not isinstance(interval, bool) and interval > 0:
        return [i * float(interval) for i in range(count)], f"{INSTRUMENT}: frames.interval_s", None
    return (
        None,
        "",
        Refusal(
            "no_frame_times",
            f"{INSTRUMENT} records no frame times for the series in {scan_set.folder!r}: "
            "frames.interval_s (s between frames) or frames.times_s "
            f"{{{scan_set.folder!r}: [...]}}. From the instrument, not from file dates.",
            ("frames.interval_s", "frames.times_s"),
        ),
    )


def _movie_series(directory: Path, record: Record, movie: Path) -> Outcome:
    """A high-speed AFM movie as one drift series, with the frame times in the file.

    The same conditions as a frame series (scan angle, closed loop, a channel
    that can be named) are required and refused the same way; the times come
    from the movie (`imaging.readers.read_stack`), which refuses a file whose
    times it would have to invent. `times_from` says so in the result.
    """
    from dobladillo.calibration.payloads import drift_payload
    from dobladillo.imaging.readers import UnreadableScan, read_stack

    base: dict[str, Any] = {"series": relative(movie, directory), "source": "movie"}
    refusal = _missing(record, "drift")
    if refusal is None:
        _, refusal = _channel(record, (movie,))
    if refusal is not None:
        return Outcome({**base, "refused": refusal.as_dict()})
    angle = angle_for(record.conditions.get("scan.angle_deg"), relative(movie, directory))
    if angle is None:
        return Outcome(
            {
                **base,
                "refused": Refusal(
                    "no_scan_angle",
                    f"{INSTRUMENT}'s scan.angle_deg gives no angle for {movie.name}",
                    ("scan.angle_deg",),
                ).as_dict(),
            }
        )
    channel, _ = _channel(record, (movie,))
    try:
        stack = read_stack(movie, channel=channel)
        payload = drift_payload(list(stack.frames), list(stack.times_s))
    except (UnreadableScan, OSError) as e:
        return Outcome({**base, "refused": Refusal("unreadable_scan", str(e)).as_dict()})
    except ValueError as e:
        return Outcome({**base, "refused": Refusal("invalid_parameters", str(e)).as_dict()})
    described = stack.describe()
    payload.update(
        {
            "movie": str(movie),
            **{k: described[k] for k in ("instrument", "channel", "scan_direction")},
            "times_source": stack.times_source,
            "file_frame_interval_s": stack.file_interval_s,
            "file_times_note": stack.times_note,
        }
    )
    base.update({"scan_angle_deg": angle, "times_from": "the movie file"})
    return Outcome({**base, "result": payload}, (movie,))


def _drift(
    directory: Path, record: Record, sets: list[ScanSet], movies: tuple[Path, ...]
) -> tuple[dict[str, Any], list[Outcome]]:
    from dobladillo.calibration.payloads import drift_payload
    from dobladillo.imaging.readers import UnreadableScan

    movie_outcomes = [_movie_series(directory, record, m) for m in movies]
    if not sets:
        return {}, movie_outcomes
    refusal = _missing(record, "drift")
    if refusal is None:
        _, refusal = _channel(record, tuple(p for s in sets for p in s.files))
    if refusal is not None:
        return {}, [
            Outcome({"series": s.name, "refused": refusal.as_dict()}) for s in sets
        ] + movie_outcomes
    channel, _ = _channel(record, tuple(p for s in sets for p in s.files))
    angle_record = record.conditions.get("scan.angle_deg")
    outcomes = []
    for scan_set in sets:
        base: dict[str, Any] = {
            "series": scan_set.name,
            "source": "frames",
            "frames": [relative(p, directory) for p in scan_set.files],
        }
        angles = {angle_for(angle_record, relative(p, directory)) for p in scan_set.files}
        if None in angles or len(angles) != 1:
            why = (
                "gives no angle for some frames"
                if None in angles
                else f"gives the frames {len(angles)} different angles"
            )
            outcomes.append(
                Outcome(
                    {
                        **base,
                        "refused": Refusal(
                            "no_scan_angle" if None in angles else "invalid_reading",
                            f"{INSTRUMENT}'s scan.angle_deg {why}: a series is one field "
                            "scanned the same way",
                            ("scan.angle_deg",),
                        ).as_dict(),
                    }
                )
            )
            continue
        times, source, times_refusal = _frame_times(record, scan_set)
        if times_refusal is not None:
            outcomes.append(Outcome({**base, "refused": times_refusal.as_dict()}))
            continue
        assert times is not None
        base.update({"scan_angle_deg": next(iter(angles)), "times_from": source})
        try:
            payload = drift_payload(_read(scan_set.files, channel), times)
        except (UnreadableScan, OSError) as e:
            outcomes.append(
                Outcome({**base, "refused": Refusal("unreadable_scan", str(e)).as_dict()})
            )
            continue
        except ValueError as e:
            outcomes.append(
                Outcome({**base, "refused": Refusal("invalid_parameters", str(e)).as_dict()})
            )
            continue
        payload["frame_files"] = [str(p) for p in scan_set.files]
        payload["times_source"] = "instrument.json"
        outcomes.append(Outcome({**base, "result": payload}, scan_set.files))
    return {}, outcomes + movie_outcomes


# ---------------------------------------------------------------- the report

NAMING: Final = (
    "during/raw/: lateral reads pattern-NN and overlap-NN (any subfolder; one calibration "
    "per subfolder, prefix and scan angle); tip reads K4's <block>-NN, e.g. staircase/S1-01; "
    "drift reads frame-NN, one series per subfolder, with frame times from "
    "instrument.json's frames; a movie (.asd, .h5-jpk) is one series, with its own frame times."
)


def run(directory: Path, options: Options | None = None) -> dict[str, Any]:
    """Every calibration the folder supports, as `post/calibration.json` holds it.

    Raises `RecordIncomplete` when nothing can be reported: no folder, no
    instrument record, no scans named by the convention, or every analysis
    refused. Otherwise returns the report, refusals included.
    """
    from dobladillo import __version__
    from dobladillo.provenance import folder_chain

    options = options or Options()
    record = read_record(directory)
    found = discover(directory)
    if not found.sets and not found.movies:
        raise RecordIncomplete(
            "no scans in during/raw/ named for a calibration. " + NAMING, kind="no_scans"
        )

    runners: dict[Analysis, Callable[[], tuple[dict[str, Any], list[Outcome]]]] = {
        "lateral": lambda: _lateral(directory, record, found.of("lateral"), options),
        "tip": lambda: _tip(directory, record, found.of("tip"), options),
        "drift": lambda: _drift(directory, record, found.of("drift"), found.movies),
    }
    analyses: dict[str, Any] = {}
    used: list[Path] = []
    refusals: list[dict[str, Any]] = []
    for analysis in ANALYSES:
        has_data = bool(found.of(analysis)) or (analysis == "drift" and bool(found.movies))
        if not has_data:
            analyses[analysis] = {"status": "no_data", "results": []}
            continue
        extra, outcomes = runners[analysis]()
        done = [o for o in outcomes if not o.refused]
        for outcome in outcomes:
            used.extend(outcome.files)
            if outcome.refused:
                name = next(
                    outcome.entry[k] for k in ("set", "scan", "series") if k in outcome.entry
                )
                refusals.append({"analysis": analysis, "of": name, **outcome.entry["refused"]})
        analyses[analysis] = {
            "status": "done"
            if done and len(done) == len(outcomes)
            else ("partial" if done else "refused"),
            **extra,
            "requires": list(REQUIRES[analysis]),
            "results": [o.entry for o in outcomes],
        }

    if not any(a["status"] in ("done", "partial") for a in analyses.values()):
        said: dict[tuple[str, str], list[str]] = {}
        for r in refusals:
            said.setdefault((r["analysis"], r["message"]), []).append(r["of"])
        raise RecordIncomplete(
            "; ".join(f"{a} {', '.join(names)}: {m}" for (a, m), names in said.items()),
            kind=refusals[0]["kind"],
        )

    conditions = record.conditions
    return {
        "written_by": f"dobladillo {__version__}",
        "naming": NAMING,
        "conditions": {
            "source": INSTRUMENT,
            "sha256": record.instrument_sha256,
            "scan": {
                name.split(".", 1)[1]: conditions.get(name)
                for name in ("scan.angle_deg", "scan.direction", "scan.closed_loop")
            }
            | {"channel": (record.data.get("scan") or {}).get("channel")},
            "deposition": {
                "mgcl2_mm": conditions.get("deposition.mgcl2_mm"),
                "nicl2_mm": conditions.get("deposition.nicl2_mm"),
            },
            "tip_part_number": _value(record, TIP_PART_FIELD.name),
            "not_recorded": list(conditions.missing),
        },
        "analyses": analyses,
        "refusals": refusals,
        "provenance": folder_chain(directory, scans=sorted(set(used))).as_dict(),
        "gate": "not evaluated: the gate is in pre/plan.md, and only a person judges it",
    }

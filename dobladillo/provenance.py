"""Content-addressed provenance: every artefact names its parent by hash.

A comparison that cannot name the exact design it tests should not be
reported. Until this module existed the link between a scan and the design it
was supposed to be of was a folder convention, and the convention had already
failed once without anything noticing: both committed experiment folders were
re-tiled after their predictions were written (see
`experiments/2026-09-22-rectangle-afm/pre/RETILED.md`). The oligos in `order/`
are of one design and `prediction.json` describes another. The predicted
dimensions happen to survive the change, and a note says so -- but a note is
the only thing that says so, and the next change might not be as harmless.

So every artefact records the hash of the one it came from::

    design -> prediction -> simulation -> order -> experiment folder -> scan -> comparison

=================  ==============================================  ==========================
node               where it is recorded, and by what               parent
=================  ==============================================  ==========================
design             nowhere as a file; every child carries its      --
                   hash (`design_sha256`)
prediction         `pre/prediction.json` ["provenance"], by        design
                   `experiment new`
simulation         the bundle's `metadata.json` ["provenance"],    design
                   by `sim bundle` / `sim sweep`
order              `pre/order/<name>_manifest.json`, by            design
                   `experiment new` and `lab order --out`
experiment folder  `pre/provenance.json`, by `experiment new`      prediction, design
scan               `post/comparison.json` ["provenance"]["scans"]  the design of the order
                   by `experiment report`                          the sample was folded from
comparison         `post/comparison.json` ["provenance"]           prediction, scans
=================  ==============================================  ==========================

**The design hash is of a canonical form, not of a file.** Two .sc files of
the same design differ byte for byte depending on who wrote them: scadnano's
writer collapses some lists onto one line and not others, the web app and the
Python library indent differently, and every file carries the version of the
library that wrote it. Hashing bytes would call one design two, and a
reformatted file would break a chain that nothing about the design had
broken. So the hash is SHA-256 over scadnano's own JSON data model, re-dumped
with sorted keys and no whitespace. Going through scadnano's serialiser rather
than walking the objects here means a field scadnano adds is covered without
anyone remembering to add it.

What is left out, and why each is not the design:

- the top-level ``version``: the writing library's version, not the design's;
- per strand and per domain, ``color``, ``name`` and ``label``: presentation;
- per strand, ``vendor`` (and the older spellings ``vendor_fields``, ``idt``):
  plate and well fields that `lab.plates` attaches when the design is
  *ordered*. If they counted, ordering a design would change its identity.

Everything else stays, including strand order. Two designs with the same
strands in a different order fold into the same object, but they give oxDNA
different particle indices, so a trajectory of one is not index-compatible
with the other. Keeping order errs towards a false mismatch, which a person
can explain, rather than a false match, which nobody would look at.

The canonical form depends on the serialiser, which is why scadnano is pinned
and why every recorded hash carries `DESIGN_HASH_SCHEME`. A hash made under
another scheme is reported as incomparable, never as a mismatch or a match.

**Legacy records are left as they are.** A `pre/prediction.json` written before
this module has no design hash, and nothing may be added to it afterwards
(`experiments/AGENTS.md`). Recording today's design hash next to it would be
worse than recording nothing: for the two folders that exist, today's design
is precisely the one the prediction was *not* made from. So such a folder gets
a record problem -- "no design hash recorded" -- in `experiment check`,
`experiment report` and the dashboard, and nothing is written into it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    import scadnano as sc

#: Names the canonicalisation below. Bump it if the canonical form changes, so
#: that hashes from the two schemes are never compared as though alike.
DESIGN_HASH_SCHEME: Final = "dobladillo-design-v1: scadnano 0.21.1 JSON, sorted keys, compact"

#: Names the layout of the records this module writes.
RECORD_SCHEME: Final = "dobladillo-provenance-v1"

#: Keys dropped from every strand and every domain: presentation and ordering.
_PRESENTATION_KEYS: Final = frozenset({"color", "name", "label", "vendor", "vendor_fields", "idt"})

#: Keys of `pre/prediction.json` left out of its content hash. The gate is the
#: one field a person is asked to write into it after `experiment new` -- the
#: file says "Write it here first" -- so it is not part of what was predicted.
#: When the gate was written is what git's timestamps are for.
PREDICTION_UNHASHED_KEYS: Final = frozenset({"gate"})

#: Written next to the files an order consists of.
ORDER_MANIFEST_SUFFIX: Final = "_manifest.json"
ORDER_MANIFEST_KIND: Final = "dobladillo order manifest"

#: The pre-registration record `experiment new` writes into `pre/`.
FOLDER_RECORD: Final = "provenance.json"


# ------------------------------------------------------------------ hashing


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """SHA-256 of a file's bytes, read in chunks so a raw AFM file is cheap."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    """One serialisation per value: sorted keys, no whitespace, ASCII only."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def canonical_design(design: sc.Design) -> dict[str, Any]:
    """The part of scadnano's JSON that is the design. See the module docstring."""
    from dobladillo import _scadnano as ad

    data = ad.design_json(design)
    data.pop("version", None)

    def strip(entry: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in entry.items() if k not in _PRESENTATION_KEYS}

    strands = []
    for strand in data.get("strands", []):
        cleaned = strip(strand)
        cleaned["domains"] = [strip(d) for d in strand.get("domains", [])]
        strands.append(cleaned)
    data["strands"] = strands
    return data


def design_sha256(design: sc.Design) -> str:
    """The design's identity. Invariant to formatting, colour and ordering fields."""
    return json_sha256(canonical_design(design))


def design_file_sha256(path: Path) -> str:
    """The design hash of a .sc file: read it back, then hash the design.

    Not the file's bytes -- a file reformatted by scadnano web hashes the same
    as the one this toolchain wrote, which is the point.
    """
    from dobladillo import _scadnano as ad

    return design_sha256(ad.read_design(path))


def prediction_sha256(prediction: dict[str, Any]) -> str:
    """Content hash of a prediction, leaving out the gate a person fills in."""
    return json_sha256({k: v for k, v in prediction.items() if k not in PREDICTION_UNHASHED_KEYS})


def short(digest: str | None) -> str:
    """The first eight hex digits, for a person. Records always hold all 64."""
    return digest[:8] if digest else "none"


# --------------------------------------------------------------- recording


def design_record(design_hash: str, *, part: str) -> dict[str, Any]:
    """How a child names its parent design."""
    return {"design_sha256": design_hash, "hash_scheme": DESIGN_HASH_SCHEME, "part": part}


def write_order_manifest(
    directory: Path, *, name: str, part: str, design_hash: str, files: list[Path]
) -> Path:
    """Tie the files of an order to the design they were generated from.

    The order is where the chain touches the physical world: the sample on the
    mica was folded from these oligos, so a scan's design is this manifest's
    design. Files are named relative to the manifest so the folder can move.
    """
    from dobladillo import __version__

    manifest = directory / f"{name}{ORDER_MANIFEST_SUFFIX}"
    record = {
        "kind": ORDER_MANIFEST_KIND,
        "scheme": RECORD_SCHEME,
        "written_by": f"dobladillo {__version__}",
        **design_record(design_hash, part=part),
        "files": {
            str(p.relative_to(directory)): file_sha256(p)
            for p in sorted(files)
            if p.resolve() != manifest.resolve()
        },
        "note": "Generated with the order. If the order files are regenerated, this is "
        "regenerated with them; editing either by hand breaks the link it records.",
    }
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    return manifest


def write_folder_record(pre: Path, *, design_hash: str, part: str) -> Path:
    """`pre/provenance.json`: the experiment folder's own node.

    Written once, by `experiment new`, straight after the prediction. It
    records the prediction's content hash, which cannot live inside the
    prediction itself, so a later edit to what was predicted is visible even
    before any data exists for git's timestamps to order it against.
    """
    from dobladillo import __version__

    prediction = json.loads((pre / "prediction.json").read_text())
    record = {
        "scheme": RECORD_SCHEME,
        "written_by": f"dobladillo {__version__}",
        "design": {"sha256": design_hash, "hash_scheme": DESIGN_HASH_SCHEME, "part": part},
        "prediction": {
            "file": "prediction.json",
            "sha256": prediction_sha256(prediction),
            "parent": design_hash,
            "excludes": sorted(PREDICTION_UNHASHED_KEYS),
        },
        "note": "Written by `dobladillo experiment new` with the prediction. Do not edit: "
        "it is how `experiment check` knows the prediction has not changed since.",
    }
    path = pre / FOLDER_RECORD
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path


def simulation_record(design: sc.Design, *, part: str, files: dict[str, Path]) -> dict[str, Any]:
    """What a job bundle's metadata carries: its design, and its inputs' hashes.

    The topology's hash is what lets `analysis.runs.check_run` tell that the
    trajectory being analysed still belongs to the design the bundle names.
    """
    return {
        "scheme": RECORD_SCHEME,
        **design_record(design_sha256(design), part=part),
        "files": {key: file_sha256(files[key]) for key in ("topology", "configuration")},
    }


# ----------------------------------------------------------------- reading


@dataclass(frozen=True)
class Link:
    """One node of the chain: what it is, its hash, and its parent's hash."""

    node: str
    name: str
    sha256: str | None
    parent: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"node": self.node, "name": self.name, "sha256": self.sha256, "parent": self.parent}


@dataclass(frozen=True)
class OrderRecord:
    manifest: str
    sha256: str
    design_sha256: str | None
    hash_scheme: str | None
    part: str | None
    #: Order files whose bytes no longer match the manifest, or are gone.
    changed: tuple[str, ...]

    @property
    def intact(self) -> bool:
        return not self.changed and self.hash_scheme == DESIGN_HASH_SCHEME

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "sha256": self.sha256,
            "design_sha256": self.design_sha256,
            "part": self.part,
            "intact": self.intact,
            "changed": list(self.changed),
        }


def read_order_manifests(order: Path) -> list[OrderRecord]:
    """Every order manifest in a directory, each checked against its files."""
    records: list[OrderRecord] = []
    if not order.is_dir():
        return records
    for path in sorted(order.glob(f"*{ORDER_MANIFEST_SUFFIX}")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("kind") != ORDER_MANIFEST_KIND:
            continue
        changed = []
        for name, digest in sorted(data.get("files", {}).items()):
            target = order / name
            if not target.is_file() or file_sha256(target) != digest:
                changed.append(name)
        records.append(
            OrderRecord(
                manifest=path.name,
                sha256=file_sha256(path),
                design_sha256=data.get("design_sha256"),
                hash_scheme=data.get("hash_scheme"),
                part=data.get("part"),
                changed=tuple(changed),
            )
        )
    return records


def raw_files(root: Path) -> list[Path]:
    """What `during/raw/` holds that counts as data (its README does not)."""
    raw = root / "during" / "raw"
    if not raw.is_dir():
        return []
    return sorted(p for p in raw.rglob("*") if p.is_file() and p.name != "README.md")


@dataclass(frozen=True)
class FolderChain:
    """An experiment folder's chain, from the design to the scans, as far as it goes."""

    root: Path
    #: The design `pre/prediction.json` says it predicts. None for a legacy record.
    predicted_design: str | None
    prediction_sha256: str | None
    folder_sha256: str | None
    orders: tuple[OrderRecord, ...]
    scans: tuple[Link, ...]
    problems: tuple[str, ...]

    @property
    def legacy(self) -> bool:
        """Written before provenance existed: the prediction names no design."""
        return self.predicted_design is None

    @property
    def scan_design(self) -> str | None:
        """The design a scan in this folder is of, if that can be established.

        A scan images a sample folded from this folder's order, so its design
        is the order's -- when there is exactly one design ordered and every
        order file still matches its manifest. Otherwise it is unknown, and
        unknown is reported, never guessed.
        """
        designs = {o.design_sha256 for o in self.orders}
        if len(designs) != 1 or not all(o.intact for o in self.orders):
            return None
        return next(iter(designs))

    @property
    def verified(self) -> bool:
        """The whole chain holds: prediction, order and scans name one design."""
        return (
            not self.legacy
            and not self.problems
            and self.scan_design is not None
            and self.scan_design == self.predicted_design
        )

    @property
    def links(self) -> tuple[Link, ...]:
        chain = [
            Link("design", "canonical scadnano JSON", self.predicted_design, None),
            Link(
                "prediction",
                "pre/prediction.json",
                self.prediction_sha256,
                self.predicted_design,
            ),
        ]
        chain += [
            Link("order", f"pre/order/{o.manifest}", o.sha256, o.design_sha256) for o in self.orders
        ]
        chain.append(
            Link(
                "experiment folder",
                f"pre/{FOLDER_RECORD}",
                self.folder_sha256,
                self.prediction_sha256,
            )
        )
        chain += list(self.scans)
        return tuple(chain)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scheme": RECORD_SCHEME,
            "hash_scheme": DESIGN_HASH_SCHEME,
            "verified": self.verified,
            "legacy": self.legacy,
            "design_sha256": self.predicted_design,
            "prediction_sha256": self.prediction_sha256,
            "folder_sha256": self.folder_sha256,
            "scan_design_sha256": self.scan_design,
            "orders": [o.as_dict() for o in self.orders],
            "scans": [s.as_dict() for s in self.scans],
            "links": [link.as_dict() for link in self.links],
            "problems": list(self.problems),
        }


def folder_chain(root: Path, *, scans: list[Path] | None = None) -> FolderChain:
    """Read an experiment folder's chain and say where it breaks.

    `scans` defaults to every data file in `during/raw/`. Problems are phrased
    as problems with the *record*, the same register as `experiments.check`,
    because that is what they are: the science may be fine, but the record
    cannot show which design it is about.
    """
    problems: list[str] = []
    pre = root / "pre"

    prediction_path = pre / "prediction.json"
    prediction: dict[str, Any] | None = None
    if prediction_path.is_file():
        try:
            loaded = json.loads(prediction_path.read_text())
            prediction = loaded if isinstance(loaded, dict) else None
        except ValueError:
            problems.append("pre/prediction.json is not valid JSON")

    predicted_design: str | None = None
    prediction_hash: str | None = None
    if prediction is not None:
        prediction_hash = prediction_sha256(prediction)
        recorded = prediction.get("provenance") or {}
        predicted_design = recorded.get("design_sha256")
        if predicted_design is None:
            message = (
                "no design hash recorded: pre/prediction.json was written before the "
                "provenance chain existed, so nothing can check that the scans are of the "
                "design that was predicted"
            )
            if (pre / "RETILED.md").is_file():
                message += (
                    ". pre/RETILED.md records that the design was changed after the "
                    "prediction was written"
                )
            problems.append(message)
        elif recorded.get("hash_scheme") != DESIGN_HASH_SCHEME:
            problems.append(
                "pre/prediction.json's design hash was made under another scheme "
                f"({recorded.get('hash_scheme')!r}); it cannot be compared with this one"
            )

    folder_hash: str | None = None
    record_path = pre / FOLDER_RECORD
    if record_path.is_file():
        folder_hash = file_sha256(record_path)
        try:
            record = json.loads(record_path.read_text())
        except ValueError:
            record = {}
            problems.append(f"pre/{FOLDER_RECORD} is not valid JSON")
        recorded_prediction = (record.get("prediction") or {}).get("sha256")
        if prediction_hash is not None and recorded_prediction not in (None, prediction_hash):
            problems.append(
                "pre/prediction.json has changed since `experiment new` recorded it (its "
                "gate aside). post/ compares against what it says now, which is not what "
                "was predicted"
            )
        recorded_design = (record.get("design") or {}).get("sha256")
        if predicted_design is not None and recorded_design not in (None, predicted_design):
            problems.append(
                f"pre/prediction.json names design {short(predicted_design)} but "
                f"pre/{FOLDER_RECORD} recorded {short(recorded_design)}"
            )
    elif predicted_design is not None:
        problems.append(
            f"pre/{FOLDER_RECORD} is missing, so whether pre/prediction.json changed after "
            "it was written cannot be checked"
        )

    order_dir = pre / "order"
    orders = tuple(read_order_manifests(order_dir))
    has_order_files = order_dir.is_dir() and any(
        p.is_file() and p.name != "README.md" for p in order_dir.rglob("*")
    )
    if has_order_files and not orders:
        problems.append(
            "pre/order has no manifest, so the order -- and every sample folded from it -- "
            "cannot be tied to a design"
        )
    for order in orders:
        if order.changed:
            problems.append(
                f"pre/order/{', '.join(order.changed)} changed since {order.manifest} was "
                f"written: the oligos may no longer be design {short(order.design_sha256)}"
            )
        if order.hash_scheme != DESIGN_HASH_SCHEME:
            problems.append(
                f"pre/order/{order.manifest} records a design hash under another scheme "
                f"({order.hash_scheme!r})"
            )
    designs = sorted({o.design_sha256 or "" for o in orders})
    if len(designs) > 1:
        problems.append(
            f"pre/order holds {len(designs)} designs ({', '.join(short(d) for d in designs)}), "
            "so a scan cannot be attributed to one of them"
        )
    elif designs and predicted_design is not None and designs[0] != predicted_design:
        problems.append(
            f"the order in pre/order is design {short(designs[0])} but the prediction is of "
            f"design {short(predicted_design)}: a sample folded from this order is not what "
            "was predicted"
        )

    chain = FolderChain(
        root=root,
        predicted_design=predicted_design,
        prediction_sha256=prediction_hash,
        folder_sha256=folder_hash,
        orders=orders,
        scans=(),
        problems=tuple(problems),
    )
    scan_design = chain.scan_design
    scan_links = tuple(
        Link("scan", _relative(path, root), file_sha256(path), scan_design)
        for path in (raw_files(root) if scans is None else scans)
        if path.is_file()
    )
    return FolderChain(
        root=root,
        predicted_design=predicted_design,
        prediction_sha256=prediction_hash,
        folder_sha256=folder_hash,
        orders=orders,
        scans=scan_links,
        problems=tuple(problems),
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)

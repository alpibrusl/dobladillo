"""A local, self-contained export archive per part, in Nanobase's layout. Never uploaded.

Results nobody can find are not results. But publishing to an external
server is outside what this toolchain does (docs/VISION.md section 0: no web
services in the loop, not for publishing either). So this writes a zip on
local disk, arranged the way Nanobase.org arranges an entry, so a person can
decide to deposit it later -- by hand, through Nanobase's own upload form,
with their own account. Nothing in this module opens a socket, and
`tests/test_licences.py` fails if anything in the package tries.

**Where the layout comes from.** Nanobase's public documentation describes an
entry's *content* but publishes no archive or file format for one:

- Poppleton, E. et al. "Nanobase.org: a repository for DNA and RNA
  nanostructures", Nucleic Acids Research 50(D1):D246-D252 (2022, online
  2021), doi:10.1093/nar/gkab1000, read at PMC8728195. It describes three upload forms -- structure
  information (a name; tags for keywords, applications and modifications; the
  molecule type, one of DNA, RNA, DNA/RNA hybrid, nucleic acid-protein hybrid
  or other; a brief description), publication information (a DOI or a manual
  citation; licensing and patent restrictions) and design and protocol
  information (the original design files, oxDNA files, protocols and results,
  images with a lead image). An entry's files are shown under tabs for
  structure designs, experimental protocols, experimental results,
  simulation protocols, simulation results and images.
- nanobase.org/tutorial (read 2026-09-28). Required: "an original design
  file (for example, a Cadnano json file)" and at least one image,
  idealised, simulated or experimental, to be the entry photo. oxDNA files
  are recommended, not required, because they drive the 3D viewer.

Read-only, both of them; no account was created and nothing was submitted.
Because neither defines an archive, **the layout below is this project's own
minimal one**, named `LAYOUT` and written into every archive so that a reader
can tell which rules it was made under. It maps one directory to each of
Nanobase's file categories and one JSON record to its three forms::

    <entry>/
      entry.json                  the three forms, a file index, provenance
      structure_designs/          scadnano .sc (the original), caDNAno v2 .json
      oxdna/                      topology .top and configuration .dat
      images/                     an idealised strand diagram, the lead image
      experimental_protocols/     plan, protocol, prediction, order (with --experiment)
      experimental_results/       comparison, measurements, report (once post/ is complete)
      simulation_protocols/       empty: no run is exported yet
      simulation_results/         empty: likewise

Every file is listed in `entry.json` with its SHA-256 and size, and every
member of the zip must be listed: `validate` checks both directions.

**Nothing is filled in for a person.** The publication form's DOI, citation,
licence and patents stay null, and applications and modifications stay
empty. Choosing a licence for a design, or saying what it is for, is a
decision about the work, not a property of it. The archive is valid without
them and says they are owed before any deposit.

**A comparison goes in only with its provenance.** An experiment's files are
included only when its chain (`dobladillo.provenance`) is verified and names
the exact design being exported. A legacy folder -- one whose prediction
records no design hash, as E1 and E2 do -- is refused rather than bundled with
a design it may not be about. That is the point of issue #13 applied at the
last step: a comparison that cannot name its design is not published, even
locally.

The archive is deterministic: fixed member timestamps, sorted members and a
PNG written without a software stamp, so exporting the same state twice gives
the same bytes and the archive's own hash is meaningful.
"""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

from dobladillo import provenance as pv

if TYPE_CHECKING:
    import scadnano as sc

#: The rules an archive was written under. Bump when they change.
LAYOUT: Final = "dobladillo-nanobase-v1"

#: The record at the root of every entry.
ENTRY_FILE: Final = "entry.json"

#: Nanobase's file categories, one directory each, in the order it lists them,
#: plus `oxdna` for the oxDNA files its upload form asks for separately.
CATEGORIES: Final[tuple[str, ...]] = (
    "structure_designs",
    "oxdna",
    "images",
    "experimental_protocols",
    "experimental_results",
    "simulation_protocols",
    "simulation_results",
)

#: The molecule types Nanobase's structure form offers.
MOLECULE_TYPES: Final = frozenset(
    {"DNA", "RNA", "DNA/RNA hybrid", "nucleic acid-protein hybrid", "other"}
)

#: Keys of the publication form. A person fills them in; this never does.
PUBLICATION_KEYS: Final = ("doi", "citation", "licence", "patents")

NEVER_UPLOADED: Final = (
    "Written locally by `dobladillo export`. dobladillo never uploads anything. To deposit "
    "this on Nanobase.org, a person uploads these files through Nanobase's own form, after "
    "filling in the publication fields left null here."
)

#: 1980-01-01, the earliest time a zip can hold: a fixed stamp makes the bytes
#: depend on the content alone.
_ZIP_EPOCH: Final = (1980, 1, 1, 0, 0, 0)


class ExportRefused(Exception):
    """The export would publish something its record cannot support."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Export:
    path: Path
    sha256: str
    entry: dict[str, Any]
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "archive": str(self.path),
            "sha256": self.sha256,
            "bytes": self.path.stat().st_size,
            "entry": self.entry["structure"]["name"],
            "layout": LAYOUT,
            "files": {c: len(self.entry["files"][c]) for c in CATEGORIES},
            "not_included": self.entry["not_included"],
            "provenance": self.entry["provenance"],
            "uploaded": False,
            "valid": self.valid,
            "problems": list(self.problems),
        }


# ------------------------------------------------------------------ writing


def strand_diagram_png(design: sc.Design, *, title: str) -> bytes:
    """An idealised strand diagram: every domain on its helix, scaffold and staples.

    Nanobase wants at least one image and accepts an idealised one. This is
    drawn from the design and nothing else, and says so on its face, so it
    cannot be mistaken for a simulation or a scan.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from dobladillo import _scadnano as ad

    data = ad.design_json(design)
    helices = max(1, len(data.get("helices", [])))
    fig, ax = plt.subplots(figsize=(9, max(2.5, 0.22 * helices + 1.2)), dpi=100)
    for strand in data.get("strands", []):
        scaffold = bool(strand.get("is_scaffold"))
        colour, width = ("#1B6C88", 1.6) if scaffold else ("#9C5412", 0.9)
        ends: list[tuple[float, float, float, float]] = []
        for domain in strand.get("domains", []):
            if "helix" not in domain:
                continue
            y = float(domain["helix"]) + (-0.12 if domain.get("forward") else 0.12)
            ax.plot([domain["start"], domain["end"]], [y, y], color=colour, lw=width)
            forward = bool(domain.get("forward"))
            five = domain["start"] if forward else domain["end"]
            three = domain["end"] if forward else domain["start"]
            ends.append((five, y, three, y))
        for (_, _, x3, y3), (x5, y5, _, _) in zip(ends, ends[1:], strict=False):
            ax.plot([x3, x5], [y3, y5], color=colour, lw=width * 0.6)
    ax.invert_yaxis()
    ax.set_xlabel("offset (bp)")
    ax.set_ylabel("helix")
    ax.set_title(f"{title}: idealised strand diagram, drawn from the design", fontsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", metadata={"Software": None})
    plt.close(fig)
    return buffer.getvalue()


def _design_files(design: sc.Design, *, name: str) -> tuple[dict[str, bytes], dict[str, str]]:
    """The .sc, caDNAno v2 and oxDNA files, as bytes keyed by archive path."""
    from dobladillo import _scadnano as ad

    files: dict[str, bytes] = {}
    missing: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        files[f"structure_designs/{name}.sc"] = ad.scadnano_text(design).encode()
        try:
            files[f"structure_designs/{name}.json"] = ad.cadnano_v2_text(design, name=name).encode()
        except (ValueError, NotImplementedError) as e:
            # The hinge's latches are extensions, which caDNAno v2 has no way
            # to say. That is a limit of the format, stated, not a failure.
            missing["cadnano_v2"] = f"not representable in caDNAno v2: {e}"
        written = ad.write_oxdna_files(design, directory=root / "oxdna", name=name)
        for path in written.values():
            files[f"oxdna/{path.name}"] = path.read_bytes()
    return files, missing


def _describe(info: dict[str, Any]) -> str:
    """A description made of facts about the design, nothing more."""
    from dobladillo import __version__

    helices = info.get("helices", info.get("arm_helices"))
    length = info.get("length_bp", info.get("arm_length_bp"))
    per_arm = " per arm" if "arm_helices" in info else ""
    scaffold = info["scaffold"]
    return (
        f"{info['lattice'].capitalize()}-lattice DNA origami: {helices} helices x {length} bp"
        f"{per_arm}, scaffold {scaffold['variant']} ({scaffold['routed_nt']} of "
        f"{scaffold['total_nt']} nt routed), {info['staple_count']} staples. "
        f"Designed with dobladillo {__version__}."
    )


def _experiment_files(
    experiment: Path, *, design_hash: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """An experiment folder's protocols and, once complete, its results.

    Refuses unless the folder's chain is verified and names `design_hash`.
    """
    chain = pv.folder_chain(experiment)
    if chain.legacy:
        raise ExportRefused(
            f"{experiment.name} records no design hash, so nothing can show its results are "
            "of this design. It is not exported; export the part without --experiment",
            kind="provenance_unverified",
        )
    if chain.predicted_design != design_hash:
        raise ExportRefused(
            f"{experiment.name} is of design {pv.short(chain.predicted_design)}, but the part "
            f"being exported is design {pv.short(design_hash)}",
            kind="design_mismatch",
        )
    if not chain.verified:
        raise ExportRefused(
            f"{experiment.name}'s provenance chain does not hold: " + "; ".join(chain.problems),
            kind="provenance_unverified",
        )

    files: dict[str, bytes] = {}
    pre = experiment / "pre"
    for name in ("plan.md", "protocol.md", "prediction.json", pv.FOLDER_RECORD):
        if (pre / name).is_file():
            files[f"experimental_protocols/{name}"] = (pre / name).read_bytes()
    order = pre / "order"
    for path in sorted(p for p in order.rglob("*") if p.is_file() and p.name != "README.md"):
        files[f"experimental_protocols/order/{path.relative_to(order).as_posix()}"] = (
            path.read_bytes()
        )

    post = experiment / "post"
    results = ("comparison.json", "measurements.json", "report.md")
    record: dict[str, Any] = {"folder": experiment.name, "chain": chain.as_dict()}
    if all((post / name).is_file() for name in results):
        comparison = json.loads((post / "comparison.json").read_text())
        compared = comparison.get("provenance") or {}
        if not compared.get("verified") or compared.get("design_sha256") != design_hash:
            raise ExportRefused(
                f"{experiment.name}/post/comparison.json does not carry a verified chain to "
                f"design {pv.short(design_hash)}; run `dobladillo experiment report` again",
                kind="provenance_unverified",
            )
        for name in results:
            files[f"experimental_results/{name}"] = (post / name).read_bytes()
        for name in ("instrument.json", "log.md"):
            source = experiment / "during" / name
            if source.is_file():
                files[f"experimental_results/{name}"] = source.read_bytes()
        record["comparison"] = compared
        record["results_included"] = True
    else:
        record["results_included"] = False
        record["results_note"] = "post/ is not complete; the comparison is added once it is"
    return files, record


def _zip(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, members[name])


def export_part(
    *,
    part: str,
    design: sc.Design,
    info: dict[str, Any],
    out: Path,
    experiment: Path | None = None,
) -> Export:
    """Write `<out>/<entry>.zip` and validate it. Talks to nothing but the disk."""
    from dobladillo import __version__

    design_hash = pv.design_sha256(design)
    entry_name = part if experiment is None else f"{part}--{experiment.name}"

    files, not_included = _design_files(design, name=part)
    files[f"images/{part}-strands.png"] = strand_diagram_png(design, title=part)
    experiment_record: dict[str, Any] | None = None
    if experiment is not None:
        extra, experiment_record = _experiment_files(experiment, design_hash=design_hash)
        files.update(extra)
    not_included.setdefault(
        "simulation", "no oxDNA run is exported; the oxdna/ files are the starting structure"
    )

    index: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
    lead = f"images/{part}-strands.png"
    for name, data in sorted(files.items()):
        category = name.split("/", 1)[0]
        record: dict[str, Any] = {
            "path": name,
            "sha256": pv.sha256_bytes(data),
            "bytes": len(data),
        }
        if name.endswith(".sc"):
            record.update(format="scadnano", original=True)
        elif category == "structure_designs" and name.endswith(".json"):
            record.update(format="cadnano_v2", original=False)
        elif name == lead:
            record.update(lead=True, kind="idealised")
        index[category].append(record)

    entry = {
        "layout": LAYOUT,
        "never_uploaded": NEVER_UPLOADED,
        "generated_by": f"dobladillo {__version__}",
        "structure": {
            "name": entry_name,
            "description": _describe(info),
            "keywords": ["DNA origami", f"{info['lattice']} lattice", part],
            "applications": [],
            "modifications": [],
            "molecule_type": "DNA",
        },
        "publication": {
            **dict.fromkeys(PUBLICATION_KEYS),
            "note": "Left for a person: a DOI, a citation, a licence for the design and any "
            "patent restriction are decisions about the work, not facts this tool knows.",
        },
        "files": index,
        "not_included": not_included,
        "provenance": {
            "design_sha256": design_hash,
            "hash_scheme": pv.DESIGN_HASH_SCHEME,
            "part": part,
            "experiment": experiment_record,
        },
    }
    members = {f"{entry_name}/{k}": v for k, v in files.items()}
    members[f"{entry_name}/{ENTRY_FILE}"] = (json.dumps(entry, indent=2) + "\n").encode()

    path = out / f"{entry_name}.zip"
    _zip(path, members)
    return Export(
        path=path, sha256=pv.file_sha256(path), entry=entry, problems=tuple(validate(path))
    )


# --------------------------------------------------------------- validating


def validate(path: Path) -> list[str]:
    """Every way `path` departs from `LAYOUT`. Empty means it conforms.

    Checks both directions -- every listed file is in the zip with the recorded
    hash, and every file in the zip is listed -- plus what Nanobase itself
    requires (an original design file, a lead image) and what this project
    does (the design file IS the design the provenance names; results only
    with a verified chain).
    """
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        return [f"not a readable zip: {e}"]
    with archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        problems: list[str] = []
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                problems.append(f"unsafe member path: {name}")
        roots = {PurePosixPath(n).parts[0] for n in names if PurePosixPath(n).parts}
        if len(roots) != 1:
            return [*problems, f"expected exactly one top-level directory, found {sorted(roots)}"]
        root = roots.pop()
        entry_path = f"{root}/{ENTRY_FILE}"
        if entry_path not in names:
            return [*problems, f"no {ENTRY_FILE} at the root of the entry"]
        try:
            entry = json.loads(archive.read(entry_path))
        except ValueError as e:
            return [*problems, f"{ENTRY_FILE} is not valid JSON: {e}"]
        if not isinstance(entry, dict):
            return [*problems, f"{ENTRY_FILE} is not an object"]
        problems += _validate_entry(entry)
        problems += _validate_files(archive, entry, root=root, names=names)
    return problems


def _validate_entry(entry: dict[str, Any]) -> list[str]:
    problems = []
    if entry.get("layout") != LAYOUT:
        problems.append(f"layout is {entry.get('layout')!r}, expected {LAYOUT!r}")
    if not entry.get("never_uploaded"):
        problems.append("the statement that this archive is local and never uploaded is missing")
    structure = entry.get("structure")
    if not isinstance(structure, dict):
        return [*problems, "no structure form"]
    if not isinstance(structure.get("name"), str) or not structure["name"]:
        problems.append("structure.name is empty")
    if not isinstance(structure.get("description"), str) or not structure["description"]:
        problems.append("structure.description is empty")
    for key in ("keywords", "applications", "modifications"):
        value = structure.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"structure.{key} must be a list of strings")
    if structure.get("molecule_type") not in MOLECULE_TYPES:
        problems.append(
            f"structure.molecule_type {structure.get('molecule_type')!r} is not one of Nanobase's"
        )
    publication = entry.get("publication")
    if not isinstance(publication, dict) or not all(k in publication for k in PUBLICATION_KEYS):
        problems.append(
            f"publication must hold {', '.join(PUBLICATION_KEYS)} (null until a person fills them)"
        )
    files = entry.get("files")
    if not isinstance(files, dict) or set(files) != set(CATEGORIES):
        problems.append(f"files must have exactly the categories {', '.join(CATEGORIES)}")
    provenance = entry.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("design_sha256"):
        problems.append("provenance.design_sha256 is missing")
    elif provenance.get("hash_scheme") != pv.DESIGN_HASH_SCHEME:
        problems.append(f"provenance.hash_scheme is {provenance.get('hash_scheme')!r}")
    return problems


def _validate_files(
    archive: zipfile.ZipFile, entry: dict[str, Any], *, root: str, names: list[str]
) -> list[str]:
    problems: list[str] = []
    files = entry.get("files")
    if not isinstance(files, dict):
        return problems
    listed: set[str] = set()
    for category, records in files.items():
        if not isinstance(records, list):
            problems.append(f"files.{category} is not a list")
            continue
        for record in records:
            name = record.get("path", "") if isinstance(record, dict) else ""
            if not name.startswith(f"{category}/"):
                problems.append(f"{name!r} is listed under {category} but is not in {category}/")
                continue
            member = f"{root}/{name}"
            if member in listed:
                problems.append(f"{name} is listed twice")
            listed.add(member)
            if member not in names:
                problems.append(f"{name} is listed but not in the archive")
                continue
            data = archive.read(member)
            if pv.sha256_bytes(data) != record.get("sha256"):
                problems.append(f"{name} does not match its recorded sha256")
            if len(data) != record.get("bytes"):
                problems.append(f"{name} is {len(data)} bytes, recorded as {record.get('bytes')}")

    unlisted = sorted(set(names) - listed - {f"{root}/{ENTRY_FILE}"})
    problems += [f"{n.split('/', 1)[1]} is in the archive but not listed" for n in unlisted]

    designs = [r for r in files.get("structure_designs", []) if isinstance(r, dict)]
    originals = [r for r in designs if r.get("original") and r.get("format") == "scadnano"]
    if not originals:
        problems.append("no original design file: Nanobase requires one (structure_designs/*.sc)")
    elif f"{root}/{originals[0].get('path')}" in names:
        problems += _design_matches(archive, f"{root}/{originals[0]['path']}", entry)
    if not any(r.get("format") == "cadnano_v2" for r in designs) and "cadnano_v2" not in entry.get(
        "not_included", {}
    ):
        problems.append("no caDNAno v2 file and no reason given in not_included")

    images = [r for r in files.get("images", []) if isinstance(r, dict)]
    if not images:
        problems.append("no image: Nanobase requires at least one, to be the entry photo")
    elif sum(1 for r in images if r.get("lead")) != 1:
        problems.append("exactly one image must be the lead image")

    oxdna = {
        PurePosixPath(r.get("path", "")).suffix
        for r in files.get("oxdna", [])
        if isinstance(r, dict)
    }
    if not {".top", ".dat"} <= oxdna:
        problems.append("oxdna/ must hold a topology (.top) and a configuration (.dat)")

    if files.get("experimental_results"):
        experiment = (entry.get("provenance") or {}).get("experiment") or {}
        compared = experiment.get("comparison") or {}
        if not compared.get("verified") or compared.get("design_sha256") != (
            entry.get("provenance") or {}
        ).get("design_sha256"):
            problems.append(
                "experimental_results are present without a verified provenance chain to "
                "this design"
            )
    return problems


def _design_matches(archive: zipfile.ZipFile, member: str, entry: dict[str, Any]) -> list[str]:
    """The .sc in the archive is the design the provenance names, by content."""
    recorded = (entry.get("provenance") or {}).get("design_sha256")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "design.sc"
        target.write_bytes(archive.read(member))
        try:
            actual = pv.design_file_sha256(target)
        except Exception as e:  # scadnano raises a variety of types on bad input
            return [f"{member.split('/', 1)[1]} cannot be read as a scadnano design: {e}"]
    if actual != recorded:
        return [
            f"{member.split('/', 1)[1]} is design {pv.short(actual)}, but provenance names "
            f"{pv.short(recorded)}"
        ]
    return []

"""The only module that talks to scadnano directly.

DESIGN.md section 10 lists scadnano API drift as a known risk. Every call goes
through here so that a breaking release is one file to fix, not a grep across
the codebase, and so that the version we were built against is stated in one
place.

Nothing in here makes design decisions. It converts, writes and reports.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import scadnano as sc

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

#: The version this adapter was written against. scadnano does not expose
#: __version__, so it is pinned in pyproject.toml and restated here for the
#: benefit of anyone reading a traceback.
SCADNANO_PINNED = "0.21.1"

#: scadnano's own idea of B-DNA geometry, read from the library rather than
#: copied, so the comparison in constants.py stays honest if it changes.
GEOMETRY = sc.Geometry()


@dataclass(frozen=True)
class ScaffoldAccounting:
    """Where every base of the scaffold went.

    Q1's acceptance criterion is that this accounting is exact, so it is a
    returned value rather than a log line: a design that silently loses
    scaffold bases is the failure being guarded against.
    """

    variant: str
    total_nt: int
    routed_nt: int
    deletions: int

    @property
    def unused_nt(self) -> int:
        """Scaffold left over, which folds as an unpaired loop."""
        return self.total_nt - self.routed_nt

    def as_dict(self) -> dict[str, Any]:
        return {**dataclasses.asdict(self), "unused_nt": self.unused_nt}


def scaffold_length(variant: str) -> int:
    """Length in nt of a named M13 variant, asked of scadnano, not remembered."""
    return len(sc.m13(variant=sc.M13Variant(variant)))


def scaffold_sequence(variant: str) -> str:
    """The whole circular scaffold, as scadnano has it, from its own origin.

    All of it, not the routed part: the bases a design leaves unrouted fold
    as a single-stranded loop, which is exactly where a stray extension could
    pair.
    """
    return str(sc.m13(variant=sc.M13Variant(variant)))


def available_scaffolds() -> dict[str, int]:
    return {v.value: len(sc.m13(variant=v)) for v in sc.M13Variant}


def new_design(*, helices: int, max_offset: int, grid: str) -> sc.Design:
    """An empty design with `helices` helices on the named grid."""
    return sc.Design(
        helices=[sc.Helix(max_offset=max_offset) for _ in range(helices)],
        grid=sc.Grid(grid),
    )


def draw(design: sc.Design, helix: int, offset: int) -> sc.StrandBuilder:
    """Start drawing a strand.

    `Design.strand` is deprecated in 0.21.1 in favour of `Design.draw_strand`,
    with identical behaviour. Absorbing that here is the whole point of this
    module: the generators say "draw" and never learn which spelling is current.
    """
    return design.draw_strand(helix, offset)


def new_design_at(*, positions: Sequence[tuple[int, int]], max_offset: int, grid: str) -> sc.Design:
    """A design whose helices sit at explicit grid positions.

    Needed wherever the cross-section is not a simple stack: a six-helix bundle
    is a ring, and where each helix sits decides which pairs are neighbours and
    therefore where a crossover is physically possible.
    """
    return sc.Design(
        helices=[sc.Helix(grid_position=p, max_offset=max_offset) for p in positions],
        grid=sc.Grid(grid),
    )


def neighbour_distance_nm(a: tuple[int, int], b: tuple[int, int], *, grid: str) -> float:
    """Centre-to-centre distance between two grid positions, in nm."""
    import math

    g = sc.Grid(grid)
    pa = sc.grid_position_to_position(a, g, GEOMETRY)
    pb = sc.grid_position_to_position(b, g, GEOMETRY)
    return math.dist((pa.x, pa.y), (pb.x, pb.y))


def interhelix_spacing_nm() -> float:
    """What scadnano considers touching neighbours, from its own geometry."""
    return float(2 * GEOMETRY.helix_radius + GEOMETRY.inter_helix_gap)


def assign_scaffold_sequence(design: sc.Design, *, variant: str, rotation: int) -> None:
    """Put the M13 sequence on whichever strand is marked as scaffold.

    Every strand's old sequence is cleared first, so this can be called again
    after the design changes -- a deletion or insertion shifts every later
    base -- and the staples are recomputed rather than left stale. Stale
    staples are what scadnano would otherwise keep, or refuse to overwrite.
    Extension sequences (latches) are part of the strands and are cleared too;
    assign them again afterwards.
    """
    for strand in design.strands:
        for domain in strand.domains:  # scadnano keeps sequences per domain
            domain.dna_sequence = None
    design.assign_m13_to_scaffold(rotation=rotation, variant=sc.M13Variant(variant))


def scaffold_strand(design: sc.Design) -> sc.Strand:
    scaffold = design.scaffold
    if scaffold is None:
        raise ValueError("design has no strand marked as scaffold")
    return scaffold


def assign_extension_sequence(
    design: sc.Design, *, min_offset: int, max_offset: int, sequence: str
) -> int:
    """Give an unpaired extension its sequence, after the scaffold has been laid.

    An extension pairs with nothing on this object, so `assign_m13_to_scaffold`
    cannot reach it. Assigning it on the builder instead does not work either:
    when a deletion falls inside the same staple, scadnano merges the
    pre-assigned strand sequence against a wildcard of the nominal length and
    raises on the off-by-one. So extensions are left blank at build time and
    filled here, keyed by the span their bound domains occupy.

    Returns the number of extensions assigned, so a caller can tell the
    difference between doing nothing and doing what it meant to.
    """
    assigned = 0
    for strand in staples(design):
        extensions = [d for d in strand.domains if isinstance(d, sc.Extension)]
        if not extensions:
            continue
        bound = [d for d in strand.domains if isinstance(d, sc.Domain)]
        if not bound or not all(min_offset <= d.start and d.end <= max_offset for d in bound):
            continue
        for extension in extensions:
            design.assign_dna(strand, sequence, assign_complement=False, domain=extension)
            assigned += 1
    return assigned


def add_extension_3p(design: sc.Design, strand: sc.Strand, *, num_bases: int) -> None:
    """Append an unpaired 3' extension to a strand that already exists.

    `StrandBuilder.extension_3p` only works while a strand is being drawn; a
    part built by scadnano's own generator (the rectangle) has no builder
    left to call it on. `Design.append_domain` is the documented way to add a
    domain afterwards, and it runs the design's own legality checks. The
    sequence is left blank, for `assign_extension_sequence`.
    """
    design.append_domain(strand, sc.Extension(num_bases=num_bases))


def oxdna_text(design: sc.Design) -> tuple[str, str]:
    """The oxDNA configuration and topology scadnano writes, as text.

    `write_oxdna_files` without the files: for reading back scadnano's own 3D
    geometry -- which face of the sheet a base points to -- rather than
    re-deriving it from its angle conventions.
    """
    dat, top = design.to_oxdna_format(warn_duplicate_strand_names=False)
    return str(dat), str(top)


def staples(design: sc.Design) -> list[sc.Strand]:
    return [s for s in design.strands if not s.is_scaffold]


def staple_lengths(design: sc.Design) -> list[int]:
    return sorted(len(s.dna_sequence or "") or s.dna_length() for s in staples(design))


def count_deletions(design: sc.Design) -> int:
    return sum(
        len(domain.deletions)
        for strand in design.strands
        for domain in strand.domains
        if isinstance(domain, sc.Domain)
    )


def nucleotide_indices(design: sc.Design) -> dict[tuple[int, int, bool], int]:
    """Map (helix, offset, forward) to the index oxDNA gives that nucleotide.

    oxDNA identifies particles by position in the topology file, and external
    forces refer to them that way, so writing a traps file needs this mapping.
    scadnano does not expose it, so it is reconstructed: strands in design
    order, domains in strand order, bases 5' to 3' within a domain, skipping
    deletions.

    The 5'-to-3' part was measured rather than assumed. Building the mapping
    both ways and checking that base-paired positions hold complementary bases
    in the written topology gives 7056 complementary and 0 inconsistent one
    way, and 5212 inconsistent the other. A test re-runs that check, because a
    silently wrong mapping would produce a traps file that restrains the wrong
    nucleotides and a relaxation that quietly pulls the structure apart.
    """
    index: dict[tuple[int, int, bool], int] = {}
    n = 0
    for strand in design.strands:
        for domain in strand.domains:
            if not hasattr(domain, "helix"):
                # A loopout or extension has no helix position, so it cannot go
                # in this map -- but it IS a particle in the topology, and the
                # counter must advance past it or every index after it is too
                # low. The hinge's two 8 nt latches made the map 16 short of
                # the topology's 9184, which would have written a traps file
                # restraining the wrong nucleotides.
                n += len(getattr(domain, "dna_sequence", "") or "")
                continue
            offsets = list(range(domain.start, domain.end))
            if not domain.forward:
                offsets.reverse()
            for offset in offsets:
                if offset in domain.deletions:
                    continue
                index[(domain.helix, offset, domain.forward)] = n
                n += 1
    return index


def extension_indices(design: sc.Design) -> list[tuple[str, tuple[int, ...]]]:
    """Every unpaired extension, as (sequence, the oxDNA indices of its bases).

    Extensions pair with nothing on their own object, so they are absent from
    `nucleotide_indices` by construction -- but they are particles, and a
    latch is made of them. This is how an observable finds one in a
    trajectory.

    Walks in exactly the same order as `nucleotide_indices`, because the two
    must agree about where every particle sits; a test asserts they partition
    the topology between them with nothing missed and nothing counted twice.
    """
    found: list[tuple[str, tuple[int, ...]]] = []
    n = 0
    for strand in design.strands:
        for domain in strand.domains:
            if not hasattr(domain, "helix"):
                sequence = getattr(domain, "dna_sequence", "") or ""
                if sequence:
                    found.append((sequence, tuple(range(n, n + len(sequence)))))
                n += len(sequence)
                continue
            for offset in range(domain.start, domain.end):
                if offset not in domain.deletions:
                    n += 1
    return found


def topology_bases(path: Path) -> list[str]:
    """The base letter of each nucleotide, in oxDNA index order."""
    lines = path.read_text().splitlines()[1:]
    return [line.split()[1] for line in lines if line.strip()]


def write_oxdna_files(design: sc.Design, *, directory: Path, name: str) -> dict[str, Path]:
    """Topology and starting configuration."""
    directory.mkdir(parents=True, exist_ok=True)
    design.write_oxdna_files(directory=str(directory), filename_no_extension=name)
    return {"topology": directory / f"{name}.top", "configuration": directory / f"{name}.dat"}


def label_for_order(
    strand: sc.Strand, *, name: str, scale: str, purification: str, plate: str, well: str
) -> None:
    """Attach the name and vendor fields an order needs.

    `vendor_fields` is a plain attribute, not a setter, and there is no
    `set_vendor_fields` despite `set_name` existing next to it. Assigning it
    directly belongs here rather than in the lab code.
    """
    strand.set_name(name)
    strand.vendor_fields = sc.VendorFields(
        scale=scale, purification=purification, plate=plate, well=well
    )


def idt_bulk_rows(design: sc.Design) -> list[str]:
    """The IDT bulk-upload text, split into rows."""
    text: str = design.to_idt_bulk_input_format(warn_duplicate_name=True)
    return text.splitlines()


def read_design(path: Path) -> sc.Design:
    """Load a design written by scadnano, or by us."""
    return sc.Design.from_scadnano_file(str(path))


def design_json(design: sc.Design) -> dict[str, Any]:
    """The design as scadnano's own JSON data model, parsed back to a dict.

    This is exactly what a .sc file holds, before any indentation is applied.
    `dobladillo.provenance` hashes a canonical form of it; going through
    scadnano's serialiser rather than walking the objects ourselves means a
    field scadnano adds is covered without anybody remembering to add it here.
    """
    import json

    parsed: dict[str, Any] = json.loads(design.to_json(suppress_indent=False))
    return parsed


def scadnano_text(design: sc.Design) -> str:
    """Exactly what `write_scadnano_file` puts in a .sc file, as text."""
    text: str = design.to_json()
    return text


def cadnano_v2_text(design: sc.Design, *, name: str) -> str:
    """The caDNAno v2 JSON, named explicitly.

    `write_cadnano_v2_file` names the design after the path it writes to, so
    the file carries the writer's directory -- a temporary one, or a home
    directory -- and two exports of one design differ. Passing the name
    keeps both the path and the variation out.

    Raises ValueError for a design caDNAno v2 cannot express (extensions).
    """
    text: str = design.to_cadnano_v2_json(name=name)
    return text


def write_all(design: sc.Design, *, directory: Path, name: str) -> dict[str, Path]:
    """Write every format Q1 needs, and say where each went.

    scadnano web opens the .sc; cadnano v2 is the interchange format the
    acceptance criterion names; oxView is for eyeballing it in 3D.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    design.write_scadnano_file(directory=str(directory), filename=f"{name}.sc")
    written["scadnano"] = directory / f"{name}.sc"

    design.write_cadnano_v2_file(directory=str(directory), filename=f"{name}.json")
    written["cadnano_v2"] = directory / f"{name}.json"

    design.write_oxview_file(directory=str(directory), filename=f"{name}.oxview")
    written["oxview"] = directory / f"{name}.oxview"

    return written


def roundtrips_through_cadnano_v2(design: sc.Design) -> bool:
    """Does this design survive a trip through cadnano v2 and back?

    The acceptance criterion says the designs must export to cadnano v2. Export
    that produces a file nobody can read back is not export, so this checks the
    round trip rather than the absence of an exception.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        design.write_cadnano_v2_file(directory=tmp, filename="roundtrip.json")
        # Takes directory and filename separately, not a path: passing a whole
        # path lands in `directory` and the error says only that exactly one of
        # json_dict or filename must be None.
        back = sc.Design.from_cadnano_v2(directory=tmp, filename="roundtrip.json")
    return len(back.strands) == len(design.strands)


def deletion_offsets(*, start: int, stop: int, period: int, phase: int = 0) -> Iterable[int]:
    """Offsets at which to delete a base, every `period` bases."""
    first = start + ((phase - start) % period)
    return range(first, stop, period)

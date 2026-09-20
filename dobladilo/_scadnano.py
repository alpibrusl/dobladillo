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
    """Put the M13 sequence on whichever strand is marked as scaffold."""
    design.assign_m13_to_scaffold(rotation=rotation, variant=sc.M13Variant(variant))


def scaffold_strand(design: sc.Design) -> sc.Strand:
    scaffold = design.scaffold
    if scaffold is None:
        raise ValueError("design has no strand marked as scaffold")
    return scaffold


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

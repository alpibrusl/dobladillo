"""What the bench needs to actually order and mix a design.

Four artefacts, all derived from the design rather than typed out:

- an IDT bulk-upload CSV and a plate spreadsheet, produced by scadnano itself
  so the format stays whatever IDT currently accepts;
- a pooling map saying which well holds which staple and, once assemblies
  exist, which part that staple belongs to;
- a pipetting sheet with volumes for the chosen scaffold concentration and
  staple excess;
- a cost estimate, stated as an estimate with its assumptions attached.

Staples are named by where they sit, `st_h03_o0096`, because a well plate whose
labels do not lead back into the design is a bag of unlabelled tubes as soon as
anything goes wrong.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import scadnano as sc

from dobladillo import _scadnano as ad
from dobladillo.constants import SCAFFOLD_CONC_NM, STAPLE_EXCESS

#: IDT synthesis scale. 25 nmol is the plate-format default and is ample for
#: origami, where each staple is used at nanomolar.
DEFAULT_SCALE = "25nm"

#: Standard desalting. Origami staples are not usually HPLC-purified: the
#: folding itself tolerates truncated by-products better than the cost does.
DEFAULT_PURIFICATION = "STD"

#: Price per base, in currency units, for plate-format oligos at the default
#: scale. NOT a quote: list prices vary by scale, purification, plate size,
#: territory and any academic discount. Overridable, and every estimate says
#: which figure it used.
DEFAULT_PRICE_PER_BASE = 0.10


def _bound(staple: sc.Strand) -> list[Any]:
    """The domains that sit on a helix.

    Extensions and loopouts have no helix and no offset. Naming or sorting a
    staple by "its domains" without this filter crashes on the first design
    that carries one -- which is every hinge, because the latch is two 3'
    extensions. `lab order` and `experiment new` had never worked for the
    hinge until a student protocol asked for it.
    """
    return [d for d in staple.domains if hasattr(d, "helix")]


def _anchor(staple: sc.Strand) -> tuple[int, int]:
    """Helix and 5' offset of the first helix-bound domain."""
    first = _bound(staple)[0]
    return first.helix, (first.start if first.forward else first.end - 1)


def staple_name(staple: sc.Strand) -> str:
    """A name that leads back to a position in the design."""
    helix, offset = _anchor(staple)
    return f"st_h{helix:02d}_o{offset:04d}"


@dataclass(frozen=True)
class Well:
    name: str
    plate: str
    well: str
    length_nt: int
    sequence: str
    helix: int
    offset: int

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CostEstimate:
    total_nt: int
    oligos: int
    price_per_base: float
    assumptions: tuple[str, ...]

    @property
    def total(self) -> float:
        return round(self.total_nt * self.price_per_base, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "oligos": self.oligos,
            "total_nt": self.total_nt,
            "price_per_base": self.price_per_base,
            "estimated_total": self.total,
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True)
class PlateLayout:
    plate_type: int
    wells: tuple[Well, ...]
    cost: CostEstimate

    @property
    def plates(self) -> list[str]:
        seen: dict[str, None] = {}
        for w in self.wells:
            seen.setdefault(w.plate, None)
        return list(seen)

    def pooling_map(self) -> dict[str, list[dict[str, Any]]]:
        """Which wells to draw from, grouped by plate.

        One part today, so every well pools into it. The grouping is here
        because it is what changes when assemblies arrive: a stage will pool
        some plates and not others.
        """
        grouped: dict[str, list[dict[str, Any]]] = {}
        for w in self.wells:
            grouped.setdefault(w.plate, []).append(
                {"well": w.well, "staple": w.name, "helix": w.helix, "offset": w.offset}
            )
        return grouped

    def as_dict(self) -> dict[str, Any]:
        return {
            "plate_type": self.plate_type,
            "plates": self.plates,
            "wells": len(self.wells),
            "cost": self.cost.as_dict(),
        }


def name_and_assign_wells(
    design: sc.Design,
    *,
    plate_type: int = 96,
    plate_prefix: str = "plate",
    scale: str = DEFAULT_SCALE,
    purification: str = DEFAULT_PURIFICATION,
    name_suffix: str = "",
) -> PlateLayout:
    """Give every staple a name, a plate and a well, in a stable order.

    Order is by helix then offset, not by whatever order the router happened to
    emit, so the same design always lands in the same wells. Re-ordering a
    plate between two orders of the same design is a quiet way to mix up a
    fridge.

    `name_suffix` and `plate_prefix` are for an order that sits next to
    another design's plates in the same fridge: E8's marked staples carry the
    position name of the E1 staple they replace, and `_hp` is what keeps the
    two tubes apart.
    """
    plate = sc.PlateCoordinate(plate_type=sc.PlateType(plate_type))
    staples = sorted(
        ad.staples(design),
        key=lambda s: (_bound(s)[0].helix, min(d.start for d in _bound(s))),
    )

    wells: list[Well] = []
    for staple in staples:
        name = staple_name(staple) + name_suffix
        plate_name = f"{plate_prefix}{plate.plate()}"
        ad.label_for_order(
            staple,
            name=name,
            scale=scale,
            purification=purification,
            plate=plate_name,
            well=plate.well(),
        )
        helix, offset = _anchor(staple)
        wells.append(
            Well(
                name=name,
                plate=plate_name,
                well=plate.well(),
                length_nt=staple.dna_length(),
                sequence=staple.dna_sequence or "",
                helix=helix,
                offset=offset,
            )
        )
        if not plate.is_last():
            plate.advance()
        else:
            plate.advance_to_next_plate()

    total_nt = sum(w.length_nt for w in wells)
    modified = sum(
        1
        for s in ad.staples(design)
        if s.modification_3p or s.modification_5p or s.modifications_int
    )
    assumptions = [
        f"{DEFAULT_PRICE_PER_BASE} per base, plate format, {scale} scale, {purification}",
        "list price, before any academic discount or territory difference",
        "synthesis only: no shipping, tax or plate handling",
    ]
    if modified:
        # No verified price per modification is held here, so it is left out
        # and said so, rather than estimated.
        assumptions.append(
            f"EXCLUDES the surcharge for {modified} modified oligos (e.g. biotin): "
            "priced per modification by the vendor, not included above"
        )
    cost = CostEstimate(
        total_nt=total_nt,
        oligos=len(wells),
        price_per_base=DEFAULT_PRICE_PER_BASE,
        assumptions=tuple(assumptions),
    )
    return PlateLayout(plate_type=plate_type, wells=tuple(wells), cost=cost)


@dataclass(frozen=True)
class SharedPool:
    """A variant that reuses another design's plates, and what it needs beyond them.

    `omit` are the base design's wells whose staples the variant replaces;
    `new` are the variant's own staples. Pool every base well except `omit`,
    plus every `new` well, and each staple is in the pool once.
    """

    base_part: str
    base_wells: int
    omit: tuple[Well, ...]
    new: int

    @property
    def pooled_staples(self) -> int:
        return self.base_wells - len(self.omit) + self.new

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_part": self.base_part,
            "base_wells": self.base_wells,
            "reused_from_base": self.base_wells - len(self.omit),
            "omit_from_base": [
                {"plate": w.plate, "well": w.well, "staple": w.name} for w in self.omit
            ],
            "new_staples": self.new,
            "pooled_staples": self.pooled_staples,
            "how": (
                f"Pool every well of the {self.base_part} plates EXCEPT the "
                f"{len(self.omit)} listed in omit_from_base, plus every well of this order. "
                f"Not the {self.base_part}'s finished pool: it already holds the unmarked "
                "version of each replaced staple, and the two would compete for the scaffold."
            ),
        }


def shared_pool(
    base: sc.Design, variant: sc.Design, *, base_part: str, plate_type: int = 96
) -> SharedPool:
    """What a variant of `base` can take from `base`'s plates, matched by sequence.

    The base's wells are assigned exactly as `name_and_assign_wells` assigns
    them for its own order -- on a copy, so the caller's design is not
    relabelled -- which is what makes the omit list match the plates in the
    fridge. Raises if the variant drops a base staple without replacing it
    one for one, because then pooling "all but these" would not give a
    complete design.
    """
    import copy

    base = copy.deepcopy(base)
    layout = name_and_assign_wells(base, plate_type=plate_type)
    variant_sequences = {s.dna_sequence for s in ad.staples(variant)}
    base_sequences = {w.sequence for w in layout.wells}
    omit = tuple(w for w in layout.wells if w.sequence not in variant_sequences)
    new = [s for s in ad.staples(variant) if s.dna_sequence not in base_sequences]
    if len(new) != len(omit):
        raise ValueError(
            f"the variant replaces {len(omit)} of {base_part}'s staples with {len(new)} of "
            "its own; a shared pool needs one for one"
        )
    return SharedPool(base_part=base_part, base_wells=len(layout.wells), omit=omit, new=len(new))


def pipetting_sheet(
    layout: PlateLayout,
    *,
    scaffold_nm: float = SCAFFOLD_CONC_NM[0],
    staple_excess: float = STAPLE_EXCESS[0],
    final_volume_ul: float = 50.0,
) -> dict[str, Any]:
    """Volumes for one folding reaction, from the defaults in constants.py.

    Deliberately reports the concentrations it assumed alongside the volumes:
    a pipetting sheet that does not say what stock it expects is a sheet that
    gets used with the wrong one.
    """
    staple_nm = scaffold_nm * staple_excess
    return {
        "final_volume_ul": final_volume_ul,
        "scaffold": {"final_nm": scaffold_nm},
        "staples": {"final_nm_each": staple_nm, "excess_over_scaffold": staple_excess},
        "distinct_staples": len(layout.wells),
        "note": (
            "volumes depend on your stock concentrations, which the design cannot know; "
            "this sheet fixes the FINAL concentrations to aim for"
        ),
    }


def write_order_files(
    design: sc.Design,
    *,
    directory: Path,
    name: str,
    plate_type: int = 96,
) -> dict[str, Path]:
    """Write the IDT files, letting scadnano own both formats."""
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    design.write_idt_bulk_input_file(
        directory=str(directory), filename=f"{name}_bulk.csv", warn_duplicate_name=True
    )
    written["idt_bulk_csv"] = directory / f"{name}_bulk.csv"

    # use_default_plates=False means "the plate and well are already on the
    # strands", which is exactly what name_and_assign_wells did. scadnano then
    # requires only_strands_with_vendor_fields, since a strand without them has
    # no well to go in; the scaffold is the one such strand here.
    design.write_idt_plate_excel_file(
        directory=str(directory),
        filename=f"{name}_plates.xlsx",
        plate_type=sc.PlateType(plate_type),
        use_default_plates=False,
        only_strands_with_vendor_fields=True,
    )
    written["idt_plate_xlsx"] = directory / f"{name}_plates.xlsx"
    return written


def bulk_csv_rows(design: sc.Design) -> Sequence[str]:
    """The bulk upload as rows, for checking without writing a file."""
    return ad.idt_bulk_rows(design)


#: Synthesis scales IDT offers for plate and tube orders. Checked against
#: rather than assumed, so a typo in a scale string is caught here instead of
#: by a rejected order.
VALID_SCALES = frozenset({"25nm", "100nm", "250nm", "1um", "4nm", "5nm", "10um"})

#: Purification codes. STD is standard desalting.
VALID_PURIFICATIONS = frozenset({"STD", "PAGE", "HPLC", "IEHPLC", "RNASE", "DUALHPLC", "PAGEHPLC"})

#: The IDT plate sheet's columns, in order.
PLATE_HEADERS = ("Well Position", "Name", "Sequence")

_DNA = frozenset("ACGT")

_MODIFICATION = re.compile(r"/[^/]+/")


def _known_modifications() -> frozenset[str]:
    """IDT codes of the modifications scadnano itself defines -- the only ones a
    part here can carry, so the only ones an order may contain."""
    return frozenset(
        m.vendor_code
        for m in (getattr(sc, n) for n in dir(sc))
        if isinstance(m, sc.Modification) and m.vendor_code
    )


def sequence_problem(sequence: str) -> str | None:
    """Why a vendor sequence is not orderable, or None: ACGT, plus known IDT
    modification codes such as "/3Bio/" at either end or inside."""
    codes = _MODIFICATION.findall(sequence)
    unknown = sorted(set(codes) - _known_modifications())
    if unknown:
        return f"unknown modification code(s) {unknown}"
    bases = _MODIFICATION.sub("", sequence).upper()
    if not bases:
        return "empty sequence"
    if not set(bases) <= _DNA:
        return f"non-DNA characters {sorted(set(bases) - _DNA)}"
    return None


@dataclass(frozen=True)
class OrderProblem:
    where: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def validate_bulk_csv(rows: Sequence[str]) -> list[OrderProblem]:
    """Check the bulk upload is one IDT would accept.

    Four fields per row, a unique non-empty name, a sequence of ACGT only, and
    a scale and purification from IDT's lists. Writing the file without an
    exception is not the same as writing one that uploads.
    """
    problems: list[OrderProblem] = []
    seen: set[str] = set()
    for i, row in enumerate(rows, start=1):
        fields = row.split(",")
        if len(fields) != 4:
            problems.append(OrderProblem(f"row {i}", f"expected 4 fields, got {len(fields)}"))
            continue
        name, sequence, scale, purification = (f.strip() for f in fields)
        if not name:
            problems.append(OrderProblem(f"row {i}", "empty name"))
        elif name in seen:
            problems.append(OrderProblem(f"row {i}", f"duplicate name {name!r}"))
        seen.add(name)
        problem = sequence_problem(sequence)
        if problem:
            problems.append(OrderProblem(f"row {i}", f"{name}: {problem}"))
        if scale not in VALID_SCALES:
            problems.append(OrderProblem(f"row {i}", f"{name}: unknown scale {scale!r}"))
        if purification not in VALID_PURIFICATIONS:
            problems.append(
                OrderProblem(f"row {i}", f"{name}: unknown purification {purification!r}")
            )
    return problems


def validate_plate_workbook(path: Path, *, plate_type: int = 96) -> list[OrderProblem]:
    """Check the plate spreadsheet: headers, well names, no duplicates."""
    import openpyxl

    problems: list[OrderProblem] = []
    workbook = openpyxl.load_workbook(path)
    rows_per_plate = 8 if plate_type == 96 else 16
    cols_per_plate = 12 if plate_type == 96 else 24
    valid_wells = {
        f"{chr(ord('A') + r)}{c}"
        for r in range(rows_per_plate)
        for c in range(1, cols_per_plate + 1)
    }

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        headers = tuple(c.value for c in sheet[1])
        if headers != PLATE_HEADERS:
            problems.append(
                OrderProblem(sheet_name, f"headers are {headers}, expected {PLATE_HEADERS}")
            )
        seen_wells: set[str] = set()
        for i, row in enumerate(sheet.iter_rows(min_row=2), start=2):
            well, name, sequence = (row[0].value, row[1].value, row[2].value)
            if well is None and name is None:
                continue
            if well not in valid_wells:
                problems.append(
                    OrderProblem(
                        f"{sheet_name}!{i}", f"well {well!r} is not on a {plate_type}-well plate"
                    )
                )
            elif well in seen_wells:
                problems.append(OrderProblem(f"{sheet_name}!{i}", f"well {well} used twice"))
            seen_wells.add(well)
            if not name:
                problems.append(OrderProblem(f"{sheet_name}!{i}", "empty name"))
            problem = sequence_problem(str(sequence or ""))
            if problem:
                problems.append(OrderProblem(f"{sheet_name}!{i}", f"{name}: {problem}"))
    return problems

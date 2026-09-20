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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import scadnano as sc

from dobladilo import _scadnano as ad
from dobladilo.constants import SCAFFOLD_CONC_NM, STAPLE_EXCESS

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


def staple_name(staple: sc.Strand) -> str:
    """A name that leads back to a position in the design."""
    first = staple.domains[0]
    offset = first.start if first.forward else first.end - 1
    return f"st_h{first.helix:02d}_o{offset:04d}"


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
) -> PlateLayout:
    """Give every staple a name, a plate and a well, in a stable order.

    Order is by helix then offset, not by whatever order the router happened to
    emit, so the same design always lands in the same wells. Re-ordering a
    plate between two orders of the same design is a quiet way to mix up a
    fridge.
    """
    plate = sc.PlateCoordinate(plate_type=sc.PlateType(plate_type))
    staples = sorted(
        ad.staples(design),
        key=lambda s: (s.domains[0].helix, min(d.start for d in s.domains)),
    )

    wells: list[Well] = []
    for staple in staples:
        name = staple_name(staple)
        plate_name = f"{plate_prefix}{plate.plate()}"
        ad.label_for_order(
            staple,
            name=name,
            scale=scale,
            purification=purification,
            plate=plate_name,
            well=plate.well(),
        )
        first = staple.domains[0]
        wells.append(
            Well(
                name=name,
                plate=plate_name,
                well=plate.well(),
                length_nt=staple.dna_length(),
                sequence=staple.dna_sequence or "",
                helix=first.helix,
                offset=first.start if first.forward else first.end - 1,
            )
        )
        if not plate.is_last():
            plate.advance()
        else:
            plate.advance_to_next_plate()

    total_nt = sum(w.length_nt for w in wells)
    cost = CostEstimate(
        total_nt=total_nt,
        oligos=len(wells),
        price_per_base=DEFAULT_PRICE_PER_BASE,
        assumptions=(
            f"{DEFAULT_PRICE_PER_BASE} per base, plate format, {scale} scale, {purification}",
            "list price, before any academic discount or territory difference",
            "synthesis only: no shipping, tax or plate handling",
        ),
    )
    return PlateLayout(plate_type=plate_type, wells=tuple(wells), cost=cost)


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
        if not sequence:
            problems.append(OrderProblem(f"row {i}", f"{name}: empty sequence"))
        elif not set(sequence.upper()) <= _DNA:
            bad = sorted(set(sequence.upper()) - _DNA)
            problems.append(OrderProblem(f"row {i}", f"{name}: non-DNA characters {bad}"))
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
            if not sequence or not set(str(sequence).upper()) <= _DNA:
                problems.append(OrderProblem(f"{sheet_name}!{i}", f"{name}: bad sequence"))
    return problems

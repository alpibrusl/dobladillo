"""Ordering variants that share a staple pool: order the difference, not the design.

docs/VISION.md s0 takes this from LegoGen's residue maps: when variants of a
shape differ only in a few strands, every other strand is identical, and a
strand library can be reused. Here that is literal. E9's two rectangles are
E1's rectangle with the 22 edge staples swapped for extended ones, so a lab
that has E1's plates orders 44 oligos, not 440, and pools the rest from the
plates it already holds.

The trap, and why the pooling instructions are explicit: a pool made for E1
contains E1's plain edge staples. Folding A from it would put the plain and
the sticky staple in competition for the same scaffold site, and a fraction
of A's mating edge would come out blunt -- capped, and ready to stack. So a
variant's pool is made from the base plates *skipping* the wells it replaces,
and the output lists them by plate and well.

This module knows nothing about origami: it compares sets of sequences and
labels strands for scadnano's order writers. `parts.dimer` supplies the sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import scadnano as sc

from dobladillo import _scadnano as ad
from dobladillo.lab.plates import (
    DEFAULT_PURIFICATION,
    DEFAULT_SCALE,
    OrderProblem,
    PlateLayout,
    Well,
    validate_bulk_csv,
    validate_plate_workbook,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class VariantPool:
    """What one variant takes from the base plates, and what it adds."""

    name: str
    #: Base wells this variant's pool draws from.
    from_base: tuple[Well, ...]
    #: Base wells it must NOT draw from: their staples are replaced or absent.
    skip: tuple[Well, ...]
    #: Sequences the base plates do not have, which must be ordered.
    extra: tuple[str, ...]

    @property
    def staples(self) -> int:
        return len(self.from_base) + len(self.extra)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "staples": self.staples,
            "from_base": len(self.from_base),
            "extra": len(self.extra),
            "skip_base_wells": [
                {"plate": w.plate, "well": w.well, "staple": w.name} for w in self.skip
            ],
        }


@dataclass(frozen=True)
class SharedPool:
    """Base plates plus per-variant extras, for a set of variants."""

    base: str
    base_wells: int
    variants: tuple[VariantPool, ...]

    @property
    def core(self) -> tuple[Well, ...]:
        """Base wells every variant uses."""
        if not self.variants:
            return ()
        shared = set.intersection(*(set(v.from_base) for v in self.variants))
        return tuple(w for w in self.variants[0].from_base if w in shared)

    def variant(self, name: str) -> VariantPool:
        for v in self.variants:
            if v.name == name:
                return v
        raise KeyError(name)

    def as_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "base_wells": self.base_wells,
            "core_wells_every_variant_uses": len(self.core),
            "variants": {v.name: v.as_dict() for v in self.variants},
            "extra_oligos_to_order": sum(len(v.extra) for v in self.variants),
        }


def shared_pool(base: str, layout: PlateLayout, variants: dict[str, frozenset[str]]) -> SharedPool:
    """Compare each variant's staple set with the base plates.

    `layout` is the base design's plate layout, as `name_and_assign_wells`
    gives it -- the plates the lab already holds. A base sequence that sits in
    two wells would make "skip this well" ambiguous, so it is refused.
    """
    by_sequence: dict[str, Well] = {}
    for well in layout.wells:
        if well.sequence in by_sequence:
            raise ValueError(
                f"{well.sequence} is in two base wells ({by_sequence[well.sequence].well}, "
                f"{well.well}); which one a variant skips would be ambiguous"
            )
        by_sequence[well.sequence] = well
    pools = []
    for name, sequences in variants.items():
        from_base = tuple(w for w in layout.wells if w.sequence in sequences)
        skip = tuple(w for w in layout.wells if w.sequence not in sequences)
        extra = tuple(sorted(s for s in sequences if s not in by_sequence))
        pools.append(VariantPool(name=name, from_base=from_base, skip=skip, extra=extra))
    return SharedPool(base=base, base_wells=len(layout.wells), variants=tuple(pools))


def label_extras(
    strands: Sequence[sc.Strand],
    *,
    names: Sequence[str],
    plate_prefix: str,
    plate_type: int = 96,
) -> list[tuple[str, str, str]]:
    """Give just these strands a name, plate and well, in the order given.

    `plates.name_and_assign_wells` labels every staple of a design; an extras
    order must label only the extras, because scadnano's writers are then
    asked for exactly the strands that carry vendor fields.
    """
    if len(strands) != len(names):
        raise ValueError("one name per strand")
    plate = sc.PlateCoordinate(plate_type=sc.PlateType(plate_type))
    placed = []
    for strand, name in zip(strands, names, strict=True):
        plate_name = f"{plate_prefix}{plate.plate()}"
        ad.label_for_order(
            strand,
            name=name,
            scale=DEFAULT_SCALE,
            purification=DEFAULT_PURIFICATION,
            plate=plate_name,
            well=plate.well(),
        )
        placed.append((name, plate_name, plate.well()))
        if not plate.is_last():
            plate.advance()
        else:
            plate.advance_to_next_plate()
    return placed


def write_labelled_order(
    design: sc.Design, *, directory: Path, name: str, plate_type: int = 96
) -> tuple[dict[str, Path], list[OrderProblem]]:
    """Write IDT files for the labelled strands only, and check both files."""
    directory.mkdir(parents=True, exist_ok=True)
    design.write_idt_bulk_input_file(
        directory=str(directory),
        filename=f"{name}_bulk.csv",
        warn_duplicate_name=True,
        only_strands_with_vendor_fields=True,
    )
    design.write_idt_plate_excel_file(
        directory=str(directory),
        filename=f"{name}_plates.xlsx",
        plate_type=sc.PlateType(plate_type),
        use_default_plates=False,
        only_strands_with_vendor_fields=True,
    )
    written = {
        "idt_bulk_csv": directory / f"{name}_bulk.csv",
        "idt_plate_xlsx": directory / f"{name}_plates.xlsx",
    }
    rows = [r for r in written["idt_bulk_csv"].read_text().splitlines() if r.strip()]
    problems = validate_bulk_csv(rows)
    problems += validate_plate_workbook(written["idt_plate_xlsx"], plate_type=plate_type)
    return written, problems

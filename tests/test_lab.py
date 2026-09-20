"""The order files are checked the way a rejected order would check them.

Writing a file without raising is not the same as writing one the vendor
accepts, so the validators are tested both ways: silent on the real output, and
firing on each way the format can be wrong.
"""

from __future__ import annotations

import pytest

from dobladilo.lab import plates as lab
from dobladilo.lab.protocol import anneal_for, folding_protocol, magnesium_screen
from dobladilo.parts.bundle import six_helix_bundle
from dobladilo.parts.rectangle import rothemund_rectangle


@pytest.fixture(scope="module")
def ordered():
    part = rothemund_rectangle()
    layout = lab.name_and_assign_wells(part.design, plate_type=96)
    return part, layout


# ------------------------------------------------------------------ plates


def test_every_staple_gets_its_own_well(ordered) -> None:
    _, layout = ordered
    seats = {(w.plate, w.well) for w in layout.wells}
    assert len(seats) == len(layout.wells)


def test_names_are_unique_and_lead_back_into_the_design(ordered) -> None:
    """A plate whose labels do not point at a position is unlabelled tubes."""
    _, layout = ordered
    assert len({w.name for w in layout.wells}) == len(layout.wells)
    for well in layout.wells:
        assert well.name == f"st_h{well.helix:02d}_o{well.offset:04d}"


def test_well_assignment_is_stable_across_runs() -> None:
    """The same design must land in the same wells, or two orders of it get
    mixed up in a fridge."""
    first = lab.name_and_assign_wells(rothemund_rectangle().design)
    second = lab.name_and_assign_wells(rothemund_rectangle().design)
    assert [(w.plate, w.well, w.name) for w in first.wells] == [
        (w.plate, w.well, w.name) for w in second.wells
    ]


def test_a_384_plate_needs_fewer_plates_than_96() -> None:
    design_96 = lab.name_and_assign_wells(rothemund_rectangle().design, plate_type=96)
    design_384 = lab.name_and_assign_wells(rothemund_rectangle().design, plate_type=384)
    assert len(design_384.plates) < len(design_96.plates)
    assert len(design_384.wells) == len(design_96.wells)


def test_cost_estimate_lands_in_the_range_the_design_doc_expects(ordered) -> None:
    """DESIGN.md section 10 says a new brick is roughly 500 to 1000 in staples.

    An independent cross-check of both the router and the price assumption: if
    this drifts far outside, one of the two is wrong and it is worth knowing
    which before an order goes out.
    """
    _, layout = ordered
    assert 400 <= layout.cost.total <= 1200


def test_cost_states_its_assumptions(ordered) -> None:
    """An estimate without its assumptions gets quoted as a price."""
    _, layout = ordered
    assert layout.cost.assumptions
    assert any("list price" in a for a in layout.cost.assumptions)


def test_pooling_map_covers_every_well(ordered) -> None:
    _, layout = ordered
    pooled = sum(len(v) for v in layout.pooling_map().values())
    assert pooled == len(layout.wells)


def test_pipetting_sheet_says_what_it_assumed(ordered) -> None:
    _, layout = ordered
    sheet = lab.pipetting_sheet(layout, scaffold_nm=10.0, staple_excess=5.0)
    assert sheet["staples"]["final_nm_each"] == 50.0
    assert sheet["note"]


# -------------------------------------------------------------- validation


def test_real_order_files_validate(tmp_path) -> None:
    part = six_helix_bundle()
    lab.name_and_assign_wells(part.design, plate_type=96)
    written = lab.write_order_files(part.design, directory=tmp_path, name="b", plate_type=96)
    assert lab.validate_bulk_csv(lab.bulk_csv_rows(part.design)) == []
    assert lab.validate_plate_workbook(written["idt_plate_xlsx"], plate_type=96) == []


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("name,ACGT,25nm", "expected 4 fields"),
        (",ACGT,25nm,STD", "empty name"),
        ("n,ACGU,25nm,STD", "non-DNA"),
        ("n,ACGT,7nm,STD", "unknown scale"),
        ("n,ACGT,25nm,SPARKLE", "unknown purification"),
        ("n,,25nm,STD", "empty sequence"),
    ],
)
def test_bulk_validator_catches_each_way_a_row_can_be_wrong(row: str, expected: str) -> None:
    problems = lab.validate_bulk_csv([row])
    assert any(expected in p.message for p in problems), problems


def test_bulk_validator_catches_duplicate_names() -> None:
    rows = ["dup,ACGT,25nm,STD", "dup,ACGT,25nm,STD"]
    assert any("duplicate" in p.message for p in lab.validate_bulk_csv(rows))


def test_plate_validator_catches_a_well_off_the_plate(tmp_path) -> None:
    """A 96-well sheet must not name wells only a 384 plate has."""
    import openpyxl

    path = tmp_path / "bad.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(lab.PLATE_HEADERS)
    sheet.append(["P24", "st_x", "ACGT"])
    book.save(path)
    problems = lab.validate_plate_workbook(path, plate_type=96)
    assert any("not on a 96-well plate" in p.message for p in problems)


def test_plate_validator_catches_wrong_headers(tmp_path) -> None:
    import openpyxl

    path = tmp_path / "bad.xlsx"
    book = openpyxl.Workbook()
    book.active.append(["Well", "Oligo", "Seq"])
    book.save(path)
    assert any("headers" in p.message for p in lab.validate_plate_workbook(path))


# --------------------------------------------------------------- protocol


def test_magnesium_screen_covers_both_ends_of_the_range() -> None:
    """Stepping by 2 from 5 stops at 19, quietly never testing the stated 20."""
    screen = magnesium_screen(low=5.0, high=20.0, step=2.0)
    assert screen[0] == 5.0
    assert screen[-1] == 20.0
    assert 19.0 in screen


def test_magnesium_screen_rejects_a_backwards_range() -> None:
    with pytest.raises(ValueError, match="below"):
        magnesium_screen(low=20.0, high=5.0)
    with pytest.raises(ValueError, match="positive"):
        magnesium_screen(step=0)


def test_three_dimensional_objects_get_the_slow_anneal() -> None:
    """The one substantive choice the sheet makes: hours, not minutes."""
    slow, fast = anneal_for("3D"), anneal_for("2D")
    assert slow.duration_h > 10 * fast.duration_h


def test_anneal_rejects_anything_but_2d_or_3d() -> None:
    with pytest.raises(ValueError, match="2D"):
        anneal_for("4D")


def test_protocol_has_one_reaction_per_magnesium_point() -> None:
    sheet = folding_protocol(part_name="p", dimensionality="3D", scaffold_variant="p7249")
    assert len(sheet["reactions"]) == len(sheet["magnesium_screen_mm"])
    assert len({r["id"] for r in sheet["reactions"]}) == len(sheet["reactions"])


def test_protocol_asks_for_the_salt_to_be_recorded() -> None:
    """oxDNA cannot model Mg2+, so a result without its salt is uncomparable."""
    sheet = folding_protocol(part_name="p", dimensionality="2D", scaffold_variant="p7249")
    assert any("MgCl2" in item for item in sheet["record_for_each_reaction"])

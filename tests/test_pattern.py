"""E8: the patterned rectangle, its order, and reading the pattern back.

Three things are pinned here, in that order. The part: that it is E1's
rectangle with only the marked staples changed, that every mark is on one
face, and what primer3 says about the hairpin. The reader: that it recovers
every way a particle can land, on synthetic scans with the answer written
down, and that an unmarked sheet never reads as marked. And the command: that
it runs on an experiment folder and refuses what it should.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from dobladillo import _scadnano as ad
from dobladillo.cli import app
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.pattern import (
    TRANSFORMS,
    GridCell,
    PatternGrid,
    background_noise_nm,
    read_cells,
    read_particle,
    readable,
    sample_cells,
    summarise,
)
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic_pattern import PatternScan, patterned_scan
from dobladillo.parts.pattern import (
    DEFAULT_PATTERN,
    MARKER_HAIRPIN,
    PatternedRectangle,
    choose_hairpin,
    circular_scaffold,
    hairpin_candidates,
    marker_faces,
    patterned_rectangle,
)
from dobladillo.parts.rectangle import rothemund_rectangle

REPO = Path(__file__).resolve().parent.parent
E1_ORDER = REPO / "experiments" / "2026-09-22-rectangle-afm" / "pre" / "order"


@pytest.fixture(scope="module")
def part() -> PatternedRectangle:
    return patterned_rectangle()


# --- the part -------------------------------------------------------------------


def test_e8_shares_every_staple_with_e1_but_the_marked_ones(part: PatternedRectangle) -> None:
    """E8 costs only its marked staples: every other staple is E1's oligo,
    byte for byte, so it comes from E1's plates. If a change to the rectangle
    or to the marking moved one unmarked staple, E8 would silently need a
    whole new order -- or, worse, be folded from E1's plates with one staple
    that no longer matches."""
    e1 = {s.dna_sequence for s in ad.staples(rothemund_rectangle().design)}
    e8 = {s.dna_sequence for s in ad.staples(part.design)}
    marked = {m.sequence for m in part.markers}
    replaced = {m.unmarked_sequence for m in part.markers}
    assert len(part.markers) == 28
    assert len(e8) == len(e1) == 220
    assert e8 - marked == e1 - replaced
    assert e1 - e8 == replaced
    assert e8 - e1 == marked
    assert part.scaffold.as_dict() == rothemund_rectangle().scaffold.as_dict()


def test_a_marked_staple_is_its_e1_staple_with_the_hairpin_on_its_3p_end(
    part: PatternedRectangle,
) -> None:
    for marker in part.markers:
        assert marker.sequence == marker.unmarked_sequence + MARKER_HAIRPIN
    assert MARKER_HAIRPIN == "TTGAGAGATGTTTTCATCTCTC"


def test_every_mark_points_off_the_same_face(part: PatternedRectangle) -> None:
    """Read from scadnano's 3D model. Every marked staple end points within
    26 degrees of +x cross +y; the edge staples, whose ends lie in the plane,
    are the only staples that do not face that side, and none is marked."""
    assert min(m.face_cos for m in part.markers) > 0.89
    faces = marker_faces(rothemund_rectangle().design)
    shapes = {
        k: tuple(d.end - d.start for d in s.domains)
        for k, s in enumerate(ad.staples(rothemund_rectangle().design))
    }
    edge = [faces[k] for k, shape in shapes.items() if shape == (16, 16)]
    interior = [faces[k] for k, shape in shapes.items() if shape != (16, 16)]
    assert len(edge) == 22 and max(edge) < 0.0 and min(edge) > -0.5
    assert min(interior) > 0.89, "an interior staple end faces the other way"


def test_the_3d_model_the_face_is_read_from_is_right_handed() -> None:
    """The face is only meaningful if the model is not a mirror image of DNA.
    Walking up a forward strand in the direction of increasing offset, the
    backbone must turn anticlockwise about that direction, by 360/10.5
    degrees per base: B-DNA is a right-handed helix."""
    design = rothemund_rectangle().design
    dat, _ = ad.oxdna_text(design)
    conf = np.array([[float(v) for v in ln.split()[:9]] for ln in dat.splitlines()[3:]])
    index = ad.nucleotide_indices(design)
    a, b, far = (index[(0, o, True)] for o in (40, 41, 300))
    axis = conf[far, :3] - conf[a, :3]
    axis /= np.linalg.norm(axis)
    u, v = -conf[a, 3:6], -conf[b, 3:6]
    u, v = u - axis * (axis @ u), v - axis * (axis @ v)
    turn = math.degrees(math.atan2(np.cross(u, v) @ axis, u @ v))
    assert turn == pytest.approx(360 / 10.5, abs=0.5)


def test_one_face_by_the_backbone_angle_model_too() -> None:
    """An independent, sign-blind check on `marker_faces`: scadnano's backbone
    angle, counting deletions as `routing.azimuth` does, with each helix
    rolled so its staple crossovers face their partners. Every interior
    staple's 3' end then sits within 45 degrees of one common direction, and
    that direction is a quarter turn from the neighbouring helix: off the
    sheet, not along it."""
    from scadnano.scadnano import angle_from_helix_to_helix, minimum_strain_angle

    from dobladillo.routing.azimuth import backbone_angle, skips

    design = rothemund_rectangle().design
    helices, geometry = design.helices, design.geometry
    deletions, insertions = skips(design)

    def angle(domain: Any, offset: int) -> float:
        h = helices[domain.helix]
        return backbone_angle(h, offset, domain.forward, geometry, deletions.get(h.idx, set()), {})

    def end(domain: Any, last: bool) -> int:
        if last:
            return int(domain.end - 1 if domain.forward else domain.start)
        return int(domain.start if domain.forward else domain.end - 1)

    pairs: dict[int, list[tuple[float, float]]] = {}
    for strand in ad.staples(design):
        for a, b in zip(strand.domains, strand.domains[1:], strict=False):
            for dom, other, last in ((a, b, True), (b, a, False)):
                target = angle_from_helix_to_helix(
                    helices[dom.helix], helices[other.helix], design.grid, geometry
                )
                pairs.setdefault(dom.helix, []).append((angle(dom, end(dom, last)) % 360, target))
    roll = {h: minimum_strain_angle(p) for h, p in pairs.items()}
    assert not insertions

    relative = []
    for strand in ad.staples(design):
        if tuple(d.end - d.start for d in strand.domains) == (16, 16):
            continue
        last = strand.domains[-1]
        up = angle_from_helix_to_helix(
            helices[last.helix],
            helices[last.helix + 1 if last.helix + 1 in helices else last.helix - 1],
            design.grid,
            geometry,
        )
        if last.helix + 1 not in helices:
            up += 180
        relative.append((angle(last, end(last, True)) + roll[last.helix] - up) % 360)
    mean = math.degrees(np.angle(np.mean(np.exp(1j * np.radians(relative)))))
    spread = [abs((r - mean + 180) % 360 - 180) for r in relative]
    assert max(spread) < 45
    assert abs(abs((mean + 180) % 360 - 180) - 90) < 20


def test_the_default_pattern_is_an_f_that_reads_one_way_only(part: PatternedRectangle) -> None:
    grid = part.grid
    assert grid.render().splitlines() == list(DEFAULT_PATTERN)
    assert grid.distances() == {
        "identity": 0,
        "rotated_180": 14,
        "mirrored_x": 14,
        "mirrored_y": 8,
    }
    assert grid.min_distance == 8 and grid.decoding_radius == 3
    assert sorted(m.cell for m in part.markers) == sorted(
        cell for cell in grid.on for _ in range(4)
    )
    # Cells about 10.5 x 12 nm, symmetric about the sheet centre.
    widths = {round(c.size_nm[0], 1) for c in grid.cells}
    assert widths <= {10.3, 10.6} and {round(c.size_nm[1], 1) for c in grid.cells} == {12.0}
    xs = sorted(round(v, 6) for c in grid.cells for v in c.x_nm)
    assert xs[0] == -xs[-1]


def test_a_pattern_that_reads_the_same_turned_round_is_refused() -> None:
    symmetric = (
        "..........",
        "...XXXX...",
        "...X..X...",
        "...XXXX...",
        "..........",
    )
    with pytest.raises(ValueError, match="half-turn or mirror"):
        patterned_rectangle(symmetric)


def test_a_mark_in_an_edge_column_is_refused() -> None:
    """The first and last columns hold edge staples, whose 3' ends lie in the
    plane: two usable ends per cell, not four."""
    edge = (
        "X.XX......",
        ".XX.......",
        ".X........",
        ".X........",
        "..........",
    )
    with pytest.raises(ValueError, match="staple ends facing"):
        patterned_rectangle(edge)


def test_a_badly_shaped_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="5 rows of 10"):
        patterned_rectangle(("XX", "X."))
    with pytest.raises(ValueError, match="no marked cell"):
        patterned_rectangle(("." * 10,) * 5)


def test_what_primer3_says_about_the_hairpin(part: PatternedRectangle) -> None:
    """Pinned, so that a change to the hairpin, the buffer, or the adapter
    shows up as a number that moved."""
    check = part.hairpin
    assert check.hairpin.tm_c == pytest.approx(69.3, abs=0.1)
    assert check.hairpin.magnesium_m == pytest.approx(0.005)
    assert check.folds_before_staples_bind
    assert check.scaffold.tm_c == pytest.approx(23.9, abs=0.1)
    assert check.worst_staple.tm_c == pytest.approx(21.7, abs=0.1)
    assert check.homodimer.tm_c == pytest.approx(45.4, abs=0.1)
    assert check.homodimer.strand_m == pytest.approx(28 * 50e-9)
    assert check.dimer_over_hairpins_kcal == pytest.approx(4.04, abs=0.02)


def test_the_stem_is_the_one_the_documented_search_chooses() -> None:
    """MARKER_STEM is not hand-picked: rerunning the seeded search with the
    stated rule returns it. About 12 s of primer3."""
    design = rothemund_rectangle().design
    candidates = hairpin_candidates(
        scaffold=circular_scaffold("p7249"),
        staples=[s.dna_sequence or "" for s in ad.staples(design)],
        copies=28,
    )
    assert choose_hairpin(candidates) == MARKER_HAIRPIN


def test_the_order_is_only_the_marked_staples(part: PatternedRectangle) -> None:
    order = part.order_design()
    assert {s.dna_sequence for s in ad.staples(order)} == {m.sequence for m in part.markers}
    assert len(ad.staples(part.design)) == 220, "ordering must not strip the part itself"


def test_the_wells_to_leave_out_are_e1s_committed_wells(part: PatternedRectangle) -> None:
    """The omit list is computed from the rectangle design, and it is only
    right if that is still the order E1 committed: same plate, same well,
    same name, same sequence as the xlsx in E1's pre/order."""
    import openpyxl

    from dobladillo.lab.plates import shared_pool

    pool = shared_pool(rothemund_rectangle().design, part.design, base_part="rectangle")
    assert (pool.base_wells, len(pool.omit), pool.new, pool.pooled_staples) == (220, 28, 28, 220)
    workbook = openpyxl.load_workbook(E1_ORDER / "rectangle_plates.xlsx")
    committed = {
        (sheet, row[0]): (row[1], row[2])
        for sheet in workbook.sheetnames
        for row in workbook[sheet].iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    replaced = {m.unmarked_sequence for m in part.markers}
    for well in pool.omit:
        assert committed[(well.plate, well.well)] == (well.name, well.sequence)
        assert well.sequence in replaced


def test_lab_order_orders_the_marks_and_names_the_wells_to_skip(tmp_path: Path) -> None:
    run = CliRunner().invoke(app, ["lab", "order", "pattern", "--out", str(tmp_path), "--json"])
    assert run.exit_code == 0, run.output
    payload = json.loads(run.stdout)
    assert payload["wells"] == 28 and payload["valid"]
    assert payload["plates"] == ["marker1"]
    assert payload["reuse"]["reused_from_base"] == 192
    assert len(payload["reuse"]["omit_from_base"]) == 28
    assert "EXCEPT" in payload["reuse"]["how"]
    rows = (tmp_path / "pattern_bulk.csv").read_text().splitlines()
    assert len(rows) == 28 and all(r.split(",")[0].endswith("_hp") for r in rows)
    assert (tmp_path / "pattern_reuse.json").is_file()


# --- the reader ------------------------------------------------------------------


def _toy_grid(on: set[tuple[int, int]]) -> PatternGrid:
    """4 x 3 cells of 10 nm, centred, with marks at the centres of `on`."""
    cells = tuple(
        GridCell(
            col=c,
            row=r,
            x_nm=(c * 10.0 - 20.0, c * 10.0 - 10.0),
            y_nm=(r * 10.0 - 15.0, r * 10.0 - 5.0),
            on=(c, r) in on,
        )
        for c in range(4)
        for r in range(3)
    )
    grid = PatternGrid(columns=4, rows=3, cells=cells)
    marks = tuple(c.centre_nm for c in grid.cells if c.on)
    return PatternGrid(columns=4, rows=3, cells=cells, marks_nm=marks)


def test_which_way_is_up_is_pinned_by_a_mark_placed_by_hand() -> None:
    """The convention every verdict rests on, fixed without the renderer: a
    sheet at 0 degrees, one mark drawn by hand to the RIGHT of centre and
    ABOVE it on the screen (smaller row index). Seen from the marked face with
    x right and y up, that is the cell at top right, and it must read the
    right way round. Drawn below centre instead, it is the mirror image."""
    grid = _toy_grid({(3, 2), (0, 1)})
    for rows_up, expected in ((True, "identity"), (False, "mirrored_y")):
        heights = np.zeros((200, 200))
        heights[60:140, 80:120] = 0.0
        centre = (100.0, 100.0)
        for x, y in grid.marks_nm:
            row = centre[0] - y if rows_up else centre[0] + y
            col = centre[1] + x
            heights[int(row) - 3 : int(row) + 4, int(col) - 3 : int(col) + 4] = 2.0
        values = sample_cells(
            HeightMap(heights_nm=heights, pixel_nm=1.0), centre_px=centre, angle_deg=0.0, grid=grid
        )
        reading = read_cells(values, grid, noise_nm=0.05)
        assert reading.transform == expected
        assert reading.distance == 0


def _read_scan(scan: PatternScan, grid: PatternGrid) -> list[tuple[str, str]]:
    """(expected, read) for every placed sheet."""
    image, background = flatten(scan.image)
    noise = background_noise_nm(image, background)
    particles = [
        p for p in find_particles(image, background, peak_percentile=50) if not p.touches_edge
    ]
    pairs = []
    for truth in scan.truth:
        nearest = min(
            particles, key=lambda p: math.dist(p.centre_px, truth.centre_px), default=None
        )
        if nearest is None or math.dist(nearest.centre_px, truth.centre_px) > 5:
            pairs.append((truth.expected, "not detected"))
            continue
        pairs.append((truth.expected, read_particle(image, nearest, grid, noise_nm=noise).verdict))
    return pairs


ALL_WAYS = [(t, "marks") for t in TRANSFORMS] + [("identity", "none"), ("rotated_180", "none")]


@pytest.mark.parametrize(
    ("mark_nm", "tip_nm", "missing"),
    [(2.0, 10.0, 0.0), (1.0, 10.0, 0.0), (1.0, 15.0, 0.2), (3.0, 10.0, 0.0), (2.0, 20.0, 0.3)],
)
def test_every_way_a_sheet_can_land_is_recovered(
    part: PatternedRectangle, mark_nm: float, tip_nm: float, missing: float
) -> None:
    """All four transforms, marked and blank, at random angles, across mark
    heights, tip radii, and a fifth to a third of marks knocked out."""
    pairs = []
    for seed in range(2):
        scan = patterned_scan(
            part.grid,
            sheet_nm=part.dimensions_nm,
            placements=ALL_WAYS,
            size_px=768,
            scan_nm=1500.0,
            mark_height_nm=mark_nm,
            tip_radius_nm=tip_nm,
            missing_fraction=missing,
            seed=seed,
        )
        assert len(scan.truth) == len(ALL_WAYS)
        pairs += _read_scan(scan, part.grid)
    wrong = [p for p in pairs if p[0] != p[1]]
    assert len(wrong) <= 1, wrong
    assert all(read in (expected, "not_found") for expected, read in wrong), (
        "a sheet read as the wrong way round, or as marked when blank"
    )


def test_marks_below_the_noise_read_blank_not_as_something_else(part: PatternedRectangle) -> None:
    """The detection floor: 0.3 nm marks at 0.12 nm noise are not seen. They
    must read blank -- not as a pattern the wrong way round."""
    scan = patterned_scan(
        part.grid,
        sheet_nm=part.dimensions_nm,
        placements=ALL_WAYS,
        size_px=768,
        scan_nm=1500.0,
        mark_height_nm=0.3,
        seed=3,
    )
    assert {read for _, read in _read_scan(scan, part.grid)} <= {"blank", "not_found"}


def test_unmarked_and_wrongly_marked_sheets_never_read_as_the_pattern(
    part: PatternedRectangle,
) -> None:
    """The negative controls. Sheets carrying OTHER patterns of seven cells,
    drawn at random, in every way round, must never read as the F: at most
    three cells wrong out of fifty is a narrow target for a random picture,
    and this checks it is narrow in practice."""
    rng = np.random.default_rng(0)
    grid = part.grid
    interior = [(c, r) for c in range(1, 9) for r in range(5)]
    found = 0
    tried = 0
    for trial in range(6):
        picked = {interior[i] for i in rng.choice(len(interior), size=7, replace=False)}
        if min(len(picked ^ grid.transform(grid.on, t)) for t in TRANSFORMS) <= 6:
            continue  # too close to the F to be a fair "other" picture
        decoy_cells = tuple(
            GridCell(c.col, c.row, c.x_nm, c.y_nm, (c.col, c.row) in picked) for c in grid.cells
        )
        decoy = PatternGrid(
            columns=grid.columns,
            rows=grid.rows,
            cells=decoy_cells,
            marks_nm=tuple(
                (x, y)
                for cell in decoy_cells
                if cell.on
                for x, y in (
                    (cell.centre_nm[0] + dx, cell.centre_nm[1] + dy)
                    for dx, dy in ((-2.6, -3.0), (2.6, -3.0), (-2.6, 3.0), (2.6, 3.0))
                )
            ),
        )
        scan = patterned_scan(
            decoy,
            sheet_nm=part.dimensions_nm,
            placements=ALL_WAYS,
            size_px=768,
            scan_nm=1500.0,
            seed=100 + trial,
        )
        for _, read in _read_scan(scan, grid):
            tried += 1
            found += read in ("pattern", "mirrored")
    assert tried >= 18
    assert found == 0


def test_tall_marks_need_the_outline_taken_at_the_plateau(part: PatternedRectangle) -> None:
    """Why E8 calls `find_particles(peak_percentile=50)`: with 3 nm marks on a
    2 nm sheet, the default 95th percentile is the top of the marks, half of
    it is the sheet's own height, and the outlines break up."""
    scan = patterned_scan(
        part.grid,
        sheet_nm=part.dimensions_nm,
        placements=[(t, "marks") for t in TRANSFORMS] * 2,
        size_px=768,
        scan_nm=1500.0,
        mark_height_nm=3.0,
        seed=1,
    )
    image, background = flatten(scan.image)

    def well_sized(particles: list[Any]) -> int:
        length, width = part.dimensions_nm
        return sum(
            abs(p.length_nm - length) < 0.2 * length and abs(p.width_nm - width) < 0.3 * width
            for p in particles
        )

    assert well_sized(find_particles(image, background, peak_percentile=50)) == len(scan.truth)
    assert well_sized(find_particles(image, background)) < len(scan.truth) / 2


def test_an_overview_scan_is_too_coarse_to_read(part: PatternedRectangle) -> None:
    coarse = HeightMap(heights_nm=np.zeros((8, 8)), pixel_nm=2000 / 512)
    fine = HeightMap(heights_nm=np.zeros((8, 8)), pixel_nm=1000 / 512)
    assert not readable(coarse, part.grid)
    assert readable(fine, part.grid)


def test_the_summary_leaves_blank_sheets_out_of_the_marked_denominator() -> None:
    grid = _toy_grid({(3, 2), (0, 1)})
    blank = read_cells(
        dict.fromkeys(((c, r) for c in range(4) for r in range(3)), 0.0), grid, noise_nm=0.1
    )
    marked = read_cells(
        {(c, r): (2.0 if (c, r) in grid.on else 0.0) for c in range(4) for r in range(3)},
        grid,
        noise_nm=0.1,
    )
    summary = summarise([blank, blank, marked])
    assert summary.counts == {"pattern": 1, "mirrored": 0, "not_found": 0, "blank": 2}
    assert summary.found.as_dict()["total"] == 3
    assert summary.found_among_marked.as_dict()["total"] == 1
    assert summary.found_among_marked.value == 1.0


# --- the command ---------------------------------------------------------------


def _e8_folder(tmp_path: Path, **overrides: Any) -> Path:
    run = CliRunner().invoke(
        app,
        [
            "experiment",
            "new",
            "2026-10-01-e8",
            "--part",
            "pattern",
            "--root",
            str(tmp_path),
            "--json",
        ],
    )
    assert run.exit_code == 0, run.output
    directory = tmp_path / "2026-10-01-e8"
    record = json.loads((directory / "during" / "instrument.json").read_text())
    record["tip"]["measured_radius_before_nm"] = 10.0
    record["tip"]["measured_radius_after_nm"] = 10.0
    record["reference"] = {"flat_height_nm": 2.0, "from": "synthetic, for a test"}
    for key, value in overrides.items():
        if key.startswith("tip."):
            record["tip"][key[4:]] = value
        else:
            record[key] = value
    (directory / "during" / "instrument.json").write_text(json.dumps(record))
    return directory


def test_experiment_new_writes_only_the_marked_order(tmp_path: Path) -> None:
    directory = _e8_folder(tmp_path)
    order = directory / "pre" / "order"
    assert len((order / "pattern_bulk.csv").read_text().splitlines()) == 28
    reuse = json.loads((order / "pattern_reuse.json").read_text())
    assert len(reuse["omit_from_base"]) == 28
    prediction = json.loads((directory / "pre" / "prediction.json").read_text())
    assert prediction["design"]["pattern"]["grid"]["decoding_radius"] == 3


def test_the_command_reads_both_samples_from_the_folder(
    tmp_path: Path, part: PatternedRectangle
) -> None:
    directory = _e8_folder(tmp_path)
    raw = directory / "during" / "raw"
    marked = [("identity", "marks"), ("rotated_180", "marks"), ("identity", "none")] * 2
    for i in range(2):
        scan = patterned_scan(
            part.grid,
            sheet_nm=part.dimensions_nm,
            placements=marked,
            size_px=768,
            scan_nm=1500.0,
            seed=i,
        )
        write_gsf(scan.image, raw / f"pattern-{i + 1:02d}.gsf")
    control = patterned_scan(
        part.grid,
        sheet_nm=part.dimensions_nm,
        placements=[("identity", "none")] * 6,
        size_px=768,
        scan_nm=1500.0,
        seed=9,
    )
    write_gsf(control.image, raw / "control-01.gsf")
    overview = patterned_scan(
        part.grid,
        sheet_nm=part.dimensions_nm,
        placements=marked,
        size_px=512,
        scan_nm=2000.0,
        seed=5,
    )
    write_gsf(overview.image, raw / "pattern-03.gsf")

    run = CliRunner().invoke(app, ["experiment", "pattern", str(directory), "--json"])
    assert run.exit_code == 0, run.output
    result = json.loads((directory / "post" / "pattern.json").read_text())
    verdicts = result["pattern"]["pattern"]["verdicts"]
    assert verdicts == {"pattern": 8, "mirrored": 0, "not_found": 0, "blank": 4}
    assert result["pattern"]["pattern"]["found_among_marked"]["fraction"] == 1.0
    assert [s["scan"].endswith("pattern-03.gsf") for s in result["pattern"]["skipped"]] == [True]
    assert result["control"]["pattern"]["verdicts"]["blank"] == 6
    assert result["provenance"]["verified"]
    assert "control_note" not in result

    report = directory / "post" / "pattern.md"
    assert "| pattern | 12 | 8 | 0 | 0 | 4 |" in report.read_text()
    report.write_text(report.read_text() + "The F is there.\n")
    again = CliRunner().invoke(app, ["experiment", "pattern", str(directory), "--json"])
    assert again.exit_code == 0
    assert report.read_text().endswith("## Interpretation\n\nThe F is there.\n")


@pytest.mark.parametrize(
    ("override", "kind"),
    [
        ({"tip.measured_radius_before_nm": None, "tip.nominal_radius_nm": 10.0}, "no_tip_radius"),
        ({"reference": {}}, "no_reference_height"),
    ],
)
def test_the_command_refuses_rather_than_substitutes(
    tmp_path: Path, override: dict[str, Any], kind: str
) -> None:
    directory = _e8_folder(tmp_path, **override)
    run = CliRunner().invoke(app, ["experiment", "pattern", str(directory), "--json"])
    assert run.exit_code != 0
    assert json.loads(run.stdout)["error"]["kind"] == kind
    assert not (directory / "post" / "pattern.json").exists()


def test_the_command_refuses_a_folder_without_a_pattern(tmp_path: Path) -> None:
    from dobladillo.experiments import scaffold

    directory = scaffold(
        tmp_path,
        slug="e1",
        prediction={"part": "rectangle", "predicted_nm": {"length": 106.2, "width": 66.0}},
        plan="# p\n",
        protocol="# p\n",
    )
    run = CliRunner().invoke(app, ["experiment", "pattern", str(directory), "--json"])
    assert json.loads(run.stdout)["error"]["kind"] == "no_pattern"


def test_secondary_structure_refuses_what_primer3_would_score_anyway() -> None:
    from dobladillo.sequence.thermo import secondary_structure

    with pytest.raises(ValueError, match="not a DNA"):
        secondary_structure("ACGU", kind="hairpin", magnesium_m=0.01)
    with pytest.raises(ValueError, match="at most 60"):
        secondary_structure("A" * 61, "T" * 61, kind="heterodimer", magnesium_m=0.01)
    with pytest.raises(ValueError, match="partner"):
        secondary_structure("ACGT", kind="heterodimer", magnesium_m=0.01)
    with pytest.raises(ValueError, match="kind"):
        secondary_structure("ACGT", kind="triplex", magnesium_m=0.01)


DRYRUN = REPO / "experiments" / "protocols" / "e8_dryrun.py"


def test_the_protocol_dry_run_passes_its_own_proposed_gate(tmp_path: Path) -> None:
    """The walk the protocol reports, rerun: every command exits cleanly
    except `experiment check`, which rightly flags an uncommitted pre/."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("e8_dryrun", DRYRUN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summary = module.run(tmp_path, mark_nm=1.0, missing=0.2, tip_nm=10.0, seed=0, realistic=True)
    steps = summary["steps"]
    assert steps["lab order"]["exit"] == 0 and steps["lab order"]["oligos"] == 28
    assert steps["experiment new"]["exit"] == 0
    assert steps["experiment pattern"]["exit"] == 0
    assert summary["pattern"]["verdicts"] == {
        "pattern": 71,
        "mirrored": 0,
        "not_found": 0,
        "blank": 71,
    }
    assert summary["control"]["verdicts"]["pattern"] == 0
    assert summary["proposed_gate"]["passes"]

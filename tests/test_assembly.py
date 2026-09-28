"""E9's analysis: assembly states from footprints, and the folder that holds them.

The measurement is a distribution, so the tests are about four things:

- the footprint windows do not overlap, at any tip radius the protocol allows;
- known mixtures are recovered inside their intervals, and a monomer-only
  sample reports few dimers -- the negative control that matters most, since
  a classifier that calls everything a dimer would pass a yield test;
- the two touching pairs are treated as the module says they are: end to end
  counts as a dimer (and the controls are what measures it), side by side is
  excluded;
- `experiment assembly` refuses rather than substituting, for every reading it
  needs.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.experiments.arms import RecordIncomplete
from dobladillo.experiments.assembly import MIN_PER_SAMPLE, analyse, new_experiment, samples_in
from dobladillo.imaging.assembly import (
    SIDE_BY_SIDE,
    STATES,
    Footprints,
    assembly_population,
    classify_assembly,
    reproducibility,
)
from dobladillo.imaging.classify import Fraction
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.particles import Particle, find_particles
from dobladillo.imaging.readers import write_gsf
from dobladillo.imaging.synthetic import synthetic_assembly_scan
from dobladillo.parts.dimer import rectangle_dimer

runner = CliRunner()

MONOMER_NM = (106.24, 66.0)
DIMER_NM = 216.48
REFERENCE_HEIGHT_NM = 2.0
TIP_NM = 10.0


def footprints(tip_radius_nm: float = TIP_NM, height_nm: float = REFERENCE_HEIGHT_NM) -> Footprints:
    return Footprints(
        monomer_length_nm=MONOMER_NM[0],
        width_nm=MONOMER_NM[1],
        dimer_length_nm=DIMER_NM,
        widening_nm=2
        * half_height_broadening_nm(tip_radius_nm=tip_radius_nm, feature_height_nm=height_nm),
        reference_height_nm=height_nm,
    )


def particle(length: float, width: float, height: float = 2.0, *, area: float | None = None):
    """A particle of stated dimensions. Area defaults to a filled rectangle."""
    return Particle(
        label=1,
        centre_px=(50.0, 50.0),
        length_nm=length,
        width_nm=width,
        height_nm=height,
        area_nm2=length * width if area is None else area,
        angle_deg=0.0,
        touches_edge=False,
    )


# --------------------------------------------------------------- the windows


def test_the_monomer_and_dimer_windows_cannot_overlap() -> None:
    """A dimer is twice as long as a monomer, so 20% either side leaves a gap
    -- but only while the tip broadening is small next to the length. Checked
    across every radius common-techniques s8 says a tip is found at."""
    for tip in (8.0, 10.0, 14.0, 20.0):
        f = footprints(tip)
        monomer_high = (1 + f.tolerance) * f.monomer_image[0]
        dimer_low = (1 - f.tolerance) * f.dimer_image[0]
        assert monomer_high < dimer_low, tip


def test_a_monomer_and_a_dimer_are_each_called_once() -> None:
    f = footprints()
    assert classify_assembly(particle(*f.monomer_image), f) == "monomer"
    assert classify_assembly(particle(*f.dimer_image), f) == "dimer"


def test_a_tall_particle_is_larger_whatever_its_footprint() -> None:
    """Height first: a stack of two sheets can have a monomer's footprint, and
    counting it as a monomer would hide exactly what the tails exist to stop."""
    f = footprints()
    assert classify_assembly(particle(*f.monomer_image, height=4.0), f) == "larger"
    assert classify_assembly(particle(*f.dimer_image, height=4.0), f) == "larger"


def test_a_trimer_is_larger_not_a_dimer() -> None:
    f = footprints()
    length = 3 * f.monomer_image[0]
    assert classify_assembly(particle(length, f.monomer_image[1]), f) == "larger"


def test_a_single_layer_covering_three_rectangles_is_larger() -> None:
    """By area, not only by length: a clump that spread sideways is not a
    dimer even when its longest extent is a dimer's."""
    f = footprints()
    wide = particle(*f.dimer_image, area=3.0 * f.unit_area_nm2)
    assert classify_assembly(wide, f) == "larger"


def test_a_sheet_of_the_wrong_shape_is_malformed() -> None:
    f = footprints()
    assert classify_assembly(particle(f.monomer_image[0], 0.5 * f.monomer_image[1]), f) == (
        "malformed"
    )


def test_side_by_side_is_excluded_rather_than_counted() -> None:
    """No designed interface makes that shape, so it is a deposition
    coincidence. Excluded from the total, and reported, so a crowded sample
    says so instead of quietly changing every fraction."""
    f = footprints()
    pair = particle(*f.side_by_side_image)
    assert classify_assembly(pair, f) == SIDE_BY_SIDE
    population = assembly_population([particle(*f.monomer_image), pair], f)
    assert population.total == 1
    assert population.excluded_side_by_side == 1
    assert population.counts["monomer"] == 1


def test_every_state_is_reported_even_when_empty() -> None:
    """The bug this repeats a guard for: a class missing from the counts
    vanished from the totals, and thirty twisted sheets counted as nothing."""
    population = assembly_population([particle(*footprints().monomer_image)], footprints())
    assert set(population.counts) == set(STATES)
    assert population.counts["larger"] == 0


# ------------------------------------------------------------------- yields


def test_the_dimer_share_carries_a_wilson_interval() -> None:
    f = footprints()
    particles = [particle(*f.monomer_image)] * 30 + [particle(*f.dimer_image)] * 10
    population = assembly_population(particles, f)
    share = population.dimer_share
    assert share == Fraction(10, 40)
    low, high = share.ci95
    assert low < 0.25 < high
    # Wilson, not the textbook interval: it never runs off the end of the scale.
    everything = assembly_population([particle(*f.dimer_image)] * 20, f)
    assert everything.dimer_share.ci95[1] == 1.0
    assert everything.dimer_share.ci95[0] < 1.0


def test_the_rectangle_fraction_maps_the_intervals_of_the_particle_fraction() -> None:
    """Rectangles in one dimer are not independent draws, so 2d/(m+2d) gets no
    interval of its own; it is a monotone function of d/(m+d), and the
    interval is mapped through it."""
    f = footprints()
    population = assembly_population(
        [particle(*f.monomer_image)] * 20 + [particle(*f.dimer_image)] * 20, f
    )
    value, (low, high) = population.rectangles_in_dimers
    assert value == pytest.approx(2 / 3)  # 20 monomers, 40 rectangles in dimers
    share_low, share_high = population.dimer_share.ci95
    assert low == pytest.approx(2 * share_low / (1 + share_low))
    assert high == pytest.approx(2 * share_high / (1 + share_high))
    assert low < value < high


def test_reproducibility_cannot_tell_identical_replicates_apart() -> None:
    f = footprints()

    def sample(monomers: int, dimers: int):
        return assembly_population(
            [particle(*f.monomer_image)] * monomers + [particle(*f.dimer_image)] * dimers, f
        )

    same = reproducibility({"R1": sample(60, 40), "R2": sample(61, 39), "R3": sample(59, 41)})
    assert same.p_value > 0.05
    assert same.largest_spread[1] < 0.05


def test_reproducibility_sees_a_replicate_that_differs() -> None:
    """The negative control. A series is meant to move; replicates are not,
    and a test that could not say so would be decoration."""
    f = footprints()

    def sample(monomers: int, dimers: int):
        return assembly_population(
            [particle(*f.monomer_image)] * monomers + [particle(*f.dimer_image)] * dimers, f
        )

    differs = reproducibility({"R1": sample(90, 10), "R2": sample(20, 80)})
    assert differs.p_value < 0.001
    assert differs.largest_spread[0] in ("monomer", "dimer")


def test_reproducibility_needs_two_samples_with_particles() -> None:
    f = footprints()
    one = assembly_population([particle(*f.monomer_image)] * 10, f)
    with pytest.raises(ValueError, match="at least two"):
        reproducibility({"R1": one})
    empty = assembly_population([], f)
    with pytest.raises(ValueError, match="at least one counted particle"):
        reproducibility({"R1": one, "R2": empty})


# ---------------------------------------------------- synthetic end to end


def _counted(**kwargs):
    scan = synthetic_assembly_scan(
        length_nm=MONOMER_NM[0], width_nm=MONOMER_NM[1], gap_nm=4.0, tip_radius_nm=TIP_NM, **kwargs
    )
    flattened, background = flatten(scan.image)
    found = find_particles(flattened, background)
    inside = [p for p in found if not p.touches_edge]
    height = statistics.median(p.height_nm for p in inside)
    return scan, assembly_population(found, footprints(TIP_NM, REFERENCE_HEIGHT_NM)), height


@pytest.mark.parametrize("monomers,dimers", [(30, 0), (20, 10), (10, 20), (0, 20)])
def test_a_known_mixture_is_recovered_within_its_interval(monomers: int, dimers: int) -> None:
    """The measurement against ground truth we chose. The rendered scan has
    scanner bow, drift and a tip streak in it, so the recovery is of the
    analysis and not of an ideal image."""
    scan, population, _ = _counted(
        monomers=monomers, dimers=dimers, seed=3, bow_nm=4.0, drift_shear=0.05, streak_lines=12
    )
    placed = Counter(p.kind for p in scan.truth)
    # The drift shear moves particles under the tip, so about one per scan ends
    # up cut by the frame and is excluded -- correctly, since it measures
    # short. Everything else must be found in the class it was placed as.
    assert population.excluded_at_edge <= 2
    for state in ("monomer", "dimer"):
        assert placed[state] - population.excluded_at_edge <= population.counts[state]
        assert population.counts[state] <= placed[state]
    assert population.counts["malformed"] == 0
    assert population.counts["larger"] == 0
    if placed["monomer"] + placed["dimer"]:
        truth = placed["dimer"] / (placed["monomer"] + placed["dimer"])
        low, high = population.dimer_share.ci95
        # Rounded at the ends: a Wilson bound at p = 1 comes back a float
        # short of 1.0, which is arithmetic rather than a missed particle.
        assert low - 1e-9 <= truth <= high + 1e-9


def test_a_monomer_only_sample_reports_no_dimers() -> None:
    """The negative control, over ten independent scans: the false-positive
    rate on a fixture whose particles are placed clear of each other must be
    zero, not merely small. Anything above it at the bench is coincidence or
    stacking, which is what E9's A-alone and B-alone controls measure."""
    total = dimers = 0
    for seed in range(10):
        _, population, _ = _counted(monomers=30, dimers=0, seed=seed)
        total += population.total
        dimers += population.counts["dimer"]
    assert total > 250
    assert dimers == 0


def test_two_monomers_touching_end_to_end_are_a_dimer_by_footprint() -> None:
    """Stated rather than hoped for. A 4 nm bridge is smaller than the tip, so
    no footprint can separate a bonded dimer from two monomers that landed in
    line -- and pretending otherwise is how a yield gets overstated."""
    _, population, _ = _counted(monomers=10, dimers=0, touching_end=6, seed=1)
    assert population.counts["dimer"] == 6
    assert population.counts["monomer"] == 10


def test_two_monomers_touching_crosswise_are_excluded() -> None:
    _, population, _ = _counted(monomers=10, dimers=0, side_by_side=6, seed=1)
    assert population.excluded_side_by_side == 6
    assert population.counts["monomer"] == 10
    assert population.total == 10


def test_aggregates_are_counted_as_larger_and_not_lost() -> None:
    """They used to be lost: a clump's own half-height threshold selected the
    substrate, the "particle" filled the frame, and being at the edge it was
    excluded. `imaging.particles` now takes the region covering its seed."""
    scan, population, _ = _counted(monomers=10, dimers=5, aggregates=4, seed=2)
    placed = Counter(p.kind for p in scan.truth)
    assert placed["aggregate"] == 4
    assert population.counts["larger"] == 4
    assert population.excluded_at_edge == 0


# --------------------------------------------------------------- the folder


@pytest.fixture(scope="module")
def dimer():
    return rectangle_dimer()


def _fill(directory: Path, samples: dict[str, tuple[int, int]], *, seed: int = 0) -> None:
    for name, (monomers, dimers) in samples.items():
        for index in (1, 2):
            scan = synthetic_assembly_scan(
                monomers=monomers,
                dimers=dimers,
                length_nm=MONOMER_NM[0],
                width_nm=MONOMER_NM[1],
                gap_nm=4.0,
                tip_radius_nm=TIP_NM,
                seed=seed + index + sum(ord(c) for c in name),
            )
            write_gsf(scan.image, directory / "during" / "raw" / f"{name}-{index:02d}.gsf")


INSTRUMENT = {
    "instrument": "test",
    "tip": {"nominal_radius_nm": 10.0, "measured_radius_before_nm": TIP_NM},
    "buffer": {"mgcl2_mm": 12.0},
    "temperature_c": 22.0,
    "reference": {"flat_height_nm": REFERENCE_HEIGHT_NM, "from": "test"},
}


@pytest.fixture
def folder(tmp_path: Path, dimer) -> Path:
    directory, _ = new_experiment(tmp_path, slug="2026-09-29-dimer", dimer=dimer)
    (directory / "during" / "instrument.json").write_text(json.dumps(INSTRUMENT))
    _fill(directory, {"A": (30, 0), "B": (30, 0), "R1": (14, 8), "R2": (14, 8)})
    return directory


def test_the_folder_records_footprints_and_no_yield(tmp_path: Path, dimer) -> None:
    """What E9 predicts is what a monomer and a dimer look like. A predicted
    yield would be a number nothing in this toolchain can compute."""
    directory, ordered = new_experiment(tmp_path, slug="2026-09-29-dimer", dimer=dimer)
    prediction = json.loads((directory / "pre" / "prediction.json").read_text())
    assert prediction["predicted_nm"]["length"] == pytest.approx(MONOMER_NM[0], abs=0.1)
    assert prediction["predicted_nm"]["dimer_length"] == pytest.approx(DIMER_NM, abs=0.1)
    assert "FILL THIS IN" in prediction["gate"]["criterion"]
    assert "No yield is predicted" in prediction["assembly"]["predicted"]
    # The order is in the folder, and its manifest names the same design.
    manifest = json.loads(Path(ordered["manifest"]).read_text())
    assert manifest["design_sha256"] == prediction["provenance"]["design_sha256"]


def test_samples_are_named_by_their_files(folder: Path) -> None:
    found = samples_in(folder)
    assert sorted(found) == ["A", "B", "R1", "R2"]
    assert all(len(v) == 2 for v in found.values())


def test_an_export_beside_a_native_file_is_not_counted_twice(folder: Path) -> None:
    """The rule `experiment report` and `compare-arms` both follow."""
    raw = folder / "during" / "raw"
    (raw / "A-01.spm").write_bytes(b"not a real Bruker file")
    assert samples_in(folder)["A"] == [raw / "A-01.spm"]


def test_a_gel_photograph_is_not_a_sample(folder: Path) -> None:
    (folder / "during" / "raw" / "gel-day1.png").write_bytes(b"png")
    assert "gel" not in samples_in(folder)


def test_the_analysis_counts_every_sample_against_the_controls(folder: Path) -> None:
    result = analyse(folder)
    assert sorted(result["samples"]) == ["A", "B", "R1", "R2"]
    assert result["samples"]["A"]["role"] == "control"
    assert result["samples"]["R1"]["role"] == "replicate"
    assert result["controls"]["dimer_fraction"]["count"] == 0
    for name in ("R1", "R2"):
        above = result["samples"][name]["dimer_minus_controls"]
        assert above["above_background"]
        assert above["ci95"][0] > 0
    assert result["reproducibility"]["p_value"] > 0.05


def test_a_series_point_is_reported_on_its_own(folder: Path) -> None:
    _fill(folder, {"T15m": (24, 3)}, seed=100)
    result = analyse(folder)
    assert result["samples"]["T15m"]["role"] == "series"
    # A series point is not a replicate, so it is not in the homogeneity test.
    assert "T15m" not in result["reproducibility"]["samples"]


def test_the_analysis_refuses_without_the_controls(folder: Path) -> None:
    for path in (folder / "during" / "raw").glob("A-*"):
        path.unlink()
    with pytest.raises(RecordIncomplete) as caught:
        analyse(folder)
    assert caught.value.kind == "no_controls"


def test_the_analysis_refuses_without_a_measured_tip_radius(folder: Path) -> None:
    """The refusal that matters most. The nominal radius is in the record and
    must not be reachable: the footprint windows are set by the measured one."""
    record = {**INSTRUMENT, "tip": {"nominal_radius_nm": 10.0}}
    (folder / "during" / "instrument.json").write_text(json.dumps(record))
    with pytest.raises(RecordIncomplete) as caught:
        analyse(folder)
    assert caught.value.kind == "no_tip_radius"
    assert "nominal" in str(caught.value)


def test_the_analysis_refuses_without_e1s_reference_height(folder: Path) -> None:
    record = {k: v for k, v in INSTRUMENT.items() if k != "reference"}
    (folder / "during" / "instrument.json").write_text(json.dumps(record))
    with pytest.raises(RecordIncomplete) as caught:
        analyse(folder)
    assert caught.value.kind == "no_reference_height"


def test_the_analysis_refuses_a_prediction_from_another_experiment(
    tmp_path: Path, folder: Path
) -> None:
    """An E1 folder has no dimer length, so there is nothing to classify
    against, and a default would invent one."""
    prediction = json.loads((folder / "pre" / "prediction.json").read_text())
    del prediction["predicted_nm"]["dimer_length"]
    (folder / "pre" / "prediction.json").write_text(json.dumps(prediction))
    with pytest.raises(RecordIncomplete) as caught:
        analyse(folder)
    assert caught.value.kind == "not_an_assembly"


# ---------------------------------------------------------------- the command


def test_the_command_writes_assembly_json(folder: Path) -> None:
    result = runner.invoke(app, ["experiment", "assembly", str(folder), "--json"])
    assert result.exit_code == 1, result.output  # fewer than 100 particles per sample
    payload = json.loads(result.stdout)
    written = json.loads((folder / "post" / "assembly.json").read_text())
    assert written["samples"].keys() == payload["samples"].keys()
    assert written["tip_radius"]["source"].startswith("mean of during/instrument.json")
    assert set(written["too_few_particles"]) == {"A", "B", "R1", "R2"}
    assert written["min_per_sample"] == MIN_PER_SAMPLE


def test_the_command_fails_with_a_structured_error(tmp_path: Path, dimer) -> None:
    """A fresh folder carries the instrument template, whose readings are all
    null. Null is absent, not zero and not the nominal value, so the command
    refuses on the tip radius -- with a `kind`, not a traceback."""
    directory, _ = new_experiment(tmp_path, slug="2026-09-29-dimer", dimer=dimer)
    result = runner.invoke(app, ["experiment", "assembly", str(directory), "--json"])
    assert result.exit_code == 1
    error = json.loads(result.stdout)["error"]
    assert error["kind"] == "no_tip_radius"

    (directory / "during" / "instrument.json").unlink()
    result = runner.invoke(app, ["experiment", "assembly", str(directory), "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "no_instrument"


def test_the_human_output_says_what_the_json_says(folder: Path) -> None:
    result = runner.invoke(app, ["experiment", "assembly", str(folder)])
    assert "controls A+B" in result.stdout
    assert "dimer above controls" in result.stdout
    assert "assembly.json" in result.stdout


def test_lab_order_dimer_says_which_staples_are_extra() -> None:
    result = runner.invoke(app, ["lab", "order", "dimer", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["extra_oligos"] == 44
    assert payload["core_wells"] == 198
    for name in ("A", "B"):
        component = payload["components"][name]
        assert len(component["extra"]) == 22
        assert {e["role"] for e in component["extra"]} == {"sticky", "passivated"}
        assert all(e["why"] for e in component["extra"])
        assert len(component["skip_e1_wells"]) == 22
    assert "Do NOT fold A or B from E1's pooled tube" in payload["warning"]


def test_the_dry_run_recovers_what_it_put_in(tmp_path: Path) -> None:
    """The whole chain on synthetic data, as E1, E2 and E4 each have. Two
    samples and two scans each rather than the script's defaults, so it stays
    a test; the script itself is what a person runs."""
    import sys

    sys.path.insert(0, "experiments/protocols")
    try:
        import e9_dryrun
    finally:
        sys.path.pop(0)

    monkeyed = {"SCANS_PER_SAMPLE": e9_dryrun.SCANS_PER_SAMPLE, "SERIES": e9_dryrun.SERIES}
    e9_dryrun.SCANS_PER_SAMPLE = 2
    e9_dryrun.SERIES = {"T1h": 0.5}
    try:
        result = e9_dryrun.run(dimer_fraction=0.6, seed=0, touching=0, root=tmp_path)
    finally:
        e9_dryrun.SCANS_PER_SAMPLE = monkeyed["SCANS_PER_SAMPLE"]
        e9_dryrun.SERIES = monkeyed["SERIES"]

    assert result["synthetic"] is True
    assert all(row["recovered"] for row in result["samples"]), result["samples"]
    assert result["gate"]["controls_dimer_fraction_at_most_0.10"]
    assert result["gate"]["every_mixture_above_controls"]
    assert result["gate"]["replicates_homogeneous"]

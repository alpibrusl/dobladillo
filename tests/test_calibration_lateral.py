"""Lateral calibration: the tile, the reference, the matcher and the scanner fit.

Every number the fit reports is checked against synthetic scans whose
scanner error was imposed (`imaging.synthetic_calibration`), including the
claim that matters most -- that the uncertainty is honest, i.e. the truth
falls inside the k = 2 interval about as often as k = 2 promises.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from dobladillo import _scadnano as ad
from dobladillo.calibration.features import detect
from dobladillo.calibration.lateral import (
    CalibrationRefused,
    LateralCalibration,
    calibrate_lateral,
    fit_scanner,
)
from dobladillo.calibration.reference import (
    Feature,
    ReferenceGeometry,
    from_tile,
    load,
)
from dobladillo.constants import INTERHELIX_SPACING_NM, RISE_PER_BP_NM, RISE_PER_BP_RANGE_NM
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.synthetic_calibration import CalibrationScan, calibration_scan
from dobladillo.parts.calibration_tile import (
    CALIBRATION_PATTERN,
    CalibrationTile,
    calibration_tile,
    isolated,
)

#: The scanner and object imposed on every synthetic scan below.
TRUTH = {"scale_x": 1.05, "scale_y": 0.97, "skew_deg": 1.5, "anisotropy": 1.08}


@pytest.fixture(scope="module")
def tile() -> CalibrationTile:
    return calibration_tile()


@pytest.fixture(scope="module")
def reference(tile: CalibrationTile) -> ReferenceGeometry:
    return from_tile(tile)


def _scans(
    tile: CalibrationTile, *, seed: int, tip_nm: float = 10.0, n: int = 20, **kw: object
) -> list[CalibrationScan]:
    """Two images of `n` tiles each, seen through the TRUTH scanner."""
    return [
        calibration_scan(
            tile.marks_nm,
            sheet_nm=tile.sheet_nm,
            n_tiles=n,
            tip_radius_nm=tip_nm,
            seed=seed * 10 + k,
            **{**TRUTH, **kw},  # type: ignore[arg-type]
        )
        for k in range(2)
    ]


def _errors(result: LateralCalibration) -> dict[str, tuple[float, float, float, float]]:
    """name: (fitted, true, u_statistical, U combined)."""
    quantities = {
        "scale_x": result.scale_x,
        "scale_y": result.scale_y,
        "skew_deg": result.skew_deg,
        "anisotropy": result.anisotropy,
    }
    return {
        name: (q.value, TRUTH[name], q.u_statistical, q.expanded) for name, q in quantities.items()
    }


# --- the tile --------------------------------------------------------------------


def test_the_tile_pattern_is_isolated_chiral_and_spread(tile: CalibrationTile) -> None:
    grid = tile.patterned.grid
    assert tile.pattern == CALIBRATION_PATTERN
    assert isolated(tile.pattern)
    # pattern.py's own check refuses < 3; this one clears it with room.
    assert grid.min_distance == 8
    assert grid.decoding_radius == 3
    # All four usable corners are marks, and the centres span the sheet.
    assert {(1, 0), (8, 0), (1, 4), (8, 4)} <= grid.on
    span_x, span_y = tile.span_nm()
    assert span_x > 0.69 * tile.sheet_nm[0]
    assert span_y > 0.72 * tile.sheet_nm[1]
    # Twelve cells, four hairpins each, like every E8 cell.
    assert len(tile.features) == 12
    assert tile.marker_count == 48
    assert all(len(f.marks_nm) == 4 for f in tile.features)


def test_a_feature_is_its_cells_centre_to_half_a_base(tile: CalibrationTile) -> None:
    """The hairpin centroid and the cell box agree; where a twist deletion
    falls in the cell they differ by half a base, and the centroid (what an
    image shows) is the one used."""
    for f in tile.features:
        assert abs(f.x_nm - f.cell_centre_nm[0]) <= tile.rise_nm / 2 + 1e-9
        assert f.y_nm == pytest.approx(f.cell_centre_nm[1])


def test_touching_marks_are_refused() -> None:
    touching = (
        ".XX.......",
        "..........",
        "....X.....",
        "..........",
        ".X.....X..",
    )
    assert not isolated(touching)
    with pytest.raises(ValueError, match="isolated"):
        calibration_tile(touching)
    assert not isolated(("..........", ".X........", "..X.......", "..........", ".......X.."))


def test_the_rulers_uncertainty_is_read_from_the_constants_ranges(tile: CalibrationTile) -> None:
    low, high = INTERHELIX_SPACING_NM
    assert tile.spacing_nm == pytest.approx((low + high) / 2)
    assert tile.spacing_relative_uncertainty == pytest.approx(
        (high - low) / 2 / math.sqrt(3) / tile.spacing_nm
    )
    assert tile.spacing_relative_uncertainty == pytest.approx(0.0417, abs=1e-4)
    # The rise is the design document's 0.34, and the whole 2.4% gap to
    # scadnano's 0.332 is the half-width of its rectangular distribution.
    assert tile.rise_nm == RISE_PER_BP_NM
    assert tile.rise_relative_uncertainty == pytest.approx(0.01358, abs=1e-5)
    # y is the weak axis by a factor of three: why the fit measures it.
    assert tile.spacing_relative_uncertainty > 3 * tile.rise_relative_uncertainty


def test_the_rise_range_is_scadnanos_value_and_ours() -> None:
    low, high = RISE_PER_BP_RANGE_NM
    assert low == pytest.approx(ad.GEOMETRY.rise_per_base_pair)
    assert high == RISE_PER_BP_NM


# --- the reference ---------------------------------------------------------------


def test_the_tile_reference_is_nominal_and_frees_y(reference: ReferenceGeometry) -> None:
    assert reference.status == "nominal"
    assert not reference.traceable
    assert reference.free_axis == "y"
    assert reference.min_spacing_nm == pytest.approx(19.4, abs=0.01)


def test_reference_json_round_trips(reference: ReferenceGeometry, tmp_path: Path) -> None:
    path = reference.save(tmp_path / "tile.json")
    back = load(path)
    assert back == reference
    assert json.loads(path.read_text())["schema"] == "dobladillo.reference/1"


def test_a_datasheet_reference_is_declared_not_built_in(tmp_path: Path) -> None:
    """A commercial sample is typed in by whoever holds its certificate; a
    'certified' one without a source is refused, and so is nonsense."""
    declared = {
        "schema": "dobladillo.reference/1",
        "name": "someone's grating, lot 42",
        "units": "nm",
        "status": "certified",
        "source": "certificate no. 0000 (as typed by the user)",
        "provenance": "user-declared",
        "relative_uncertainty": {"x": 0.002, "y": 0.002},
        "features": [
            {"name": "a", "x_nm": 0.0, "y_nm": 0.0},
            {"name": "b", "x_nm": 100.0, "y_nm": 0.0},
            {"name": "c", "x_nm": 0.0, "y_nm": 70.0},
        ],
    }
    (tmp_path / "ref.json").write_text(json.dumps(declared))
    ref = load(tmp_path / "ref.json")
    assert ref.traceable
    assert ref.free_axis is None
    with pytest.raises(ValueError, match="source"):
        ReferenceGeometry.from_dict({**declared, "source": None})
    with pytest.raises(ValueError, match="collinear"):
        ReferenceGeometry(
            name="line",
            features=tuple(Feature(str(i), float(i), 0.0) for i in range(4)),
            relative_uncertainty=(0.0, 0.0),
            status="nominal",
            provenance="",
        )
    with pytest.raises(ValueError, match="schema"):
        ReferenceGeometry.from_dict({**declared, "schema": "something else"})


# --- the scanner fit -------------------------------------------------------------


@pytest.mark.parametrize("tip_nm", [5.0, 15.0])
def test_the_imposed_scanner_is_recovered(
    tile: CalibrationTile, reference: ReferenceGeometry, tip_nm: float
) -> None:
    """sx 1.05, sy 0.97, skew 1.5 deg, anisotropy 1.08; 40 tiles in two images.

    Measured (seed 1), fitted (statistical u):
    5 nm tip:  sx 1.04989 (0.00020), sy 0.97003 (0.00013),
               skew 1.5012 (0.0128) deg, a 1.08000 (0.00026)
    15 nm tip: sx 1.04979 (0.00023), sy 0.96990 (0.00022),
               skew 1.4996 (0.0173) deg, a 1.08018 (0.00033)
    Every error within one statistical u. The combined U (k=2) is about
    0.028 on the scales and the anisotropy, carried by the rise's 2.4%
    range, which passes one for one into the scanner's scales.
    """
    result, detections = calibrate_lateral(
        [s.image for s in _scans(tile, seed=1, tip_nm=tip_nm)], reference
    )
    assert result.n_particles == 40
    assert all(not d.rejected for d in detections)
    for name, (fitted, true, u_stat, expanded) in _errors(result).items():
        assert abs(fitted - true) <= expanded, name
        # And well inside the statistical interval alone, which is the
        # sharper test: the combined one is dominated by the reference.
        assert abs(fitted - true) <= 3 * u_stat, (name, fitted, true, u_stat)
    assert result.residual_rms_nm.value < 0.3
    rise = reference.relative_uncertainty[0]
    assert result.scale_x.u_reference_scale == pytest.approx(1.05 * rise, rel=0.02)
    assert result.scale_y.u_reference_scale == pytest.approx(0.97 * rise, rel=0.02)
    assert not result.traceable
    assert result.as_dict()["traceable"] is False
    json.dumps(result.as_dict())


def test_centroids_do_not_move_with_the_tip(
    tile: CalibrationTile, reference: ReferenceGeometry
) -> None:
    """The same tiles imaged with a 5 and a 15 nm tip: every mark's centroid
    agrees to a small fraction of a nanometre, while the outline widens by
    several. This is why the ruler is marks, not edges. Measured: 144 marks
    on 12 tiles move 0.11 nm rms (at most 0.27 nm, no common shift), while
    the half-height width grows from 65.6 to 70.5 nm."""
    sharp, blunt = (
        calibration_scan(
            tile.marks_nm, sheet_nm=tile.sheet_nm, n_tiles=12, tip_radius_nm=r, seed=3, **TRUTH
        )
        for r in (5.0, 15.0)
    )
    assert [t.centre_px for t in sharp.truth] == [t.centre_px for t in blunt.truth]
    marks = []
    for scan in (sharp, blunt):
        found = {}
        for m in detect(scan.image, reference).matches:
            centre = tuple(m.observed_nm.mean(axis=0).round(-1))
            for name, xy in zip(m.names, m.observed_nm, strict=True):
                found[(centre, name)] = xy
        marks.append(found)
    shared = marks[0].keys() & marks[1].keys()
    assert len(shared) >= 0.9 * 12 * len(sharp.truth)
    moved = np.array([np.hypot(*(marks[0][k] - marks[1][k])) for k in shared])
    assert float(np.sqrt((moved**2).mean())) < 0.25

    def widths(scan: CalibrationScan) -> float:
        image, background = flatten(scan.image)
        found = find_particles(image, background, peak_percentile=50)
        return float(np.median([p.width_nm for p in found if not p.touches_edge]))

    assert widths(blunt) - widths(sharp) > 3.0


def test_the_uncertainty_is_honest(tile: CalibrationTile, reference: ReferenceGeometry) -> None:
    """Ten independent sessions: the truth lies within the STATISTICAL k=2
    interval at least 8 times in 10 for every quantity (measured: 10, 10, 9, 8
    for sx, sy, skew, a at bootstrap 100), and within the combined interval
    every time for the scales and the anisotropy.

    Not pinned here because it takes minutes: over 30 other sessions
    (bootstrap 60) the statistical interval covered 27, 28, 27, 27 of 30,
    and the errors spread 1.13-1.22 times the reported u. The bootstrap reads
    about 15% low; `lateral.NOT_INCLUDED` says so in every result."""
    covered = dict.fromkeys(TRUTH, 0)
    combined = dict.fromkeys(TRUTH, 0)
    for seed in range(10):
        scans = _scans(tile, seed=100 + seed, n=24)
        result, _ = calibrate_lateral([s.image for s in scans], reference, bootstrap=100)
        for name, (fitted, true, u_stat, expanded) in _errors(result).items():
            covered[name] += abs(fitted - true) <= 2 * u_stat
            combined[name] += abs(fitted - true) <= expanded
    assert all(n >= 8 for n in covered.values()), covered
    # Skew has no reference component (a stretched reference leaves angles
    # alone), so its combined interval is its statistical one.
    assert combined["skew_deg"] == covered["skew_deg"]
    assert all(combined[name] == 10 for name in ("scale_x", "scale_y", "anisotropy")), combined


def test_the_budget_follows_the_reference(tile: CalibrationTile) -> None:
    """A certified reference with the anisotropy fixed: traceable, and its y
    uncertainty now a component; a per-feature uncertainty adds a third."""
    base = from_tile(tile)
    certified = ReferenceGeometry(
        name="certified tile (hypothetical)",
        features=base.features,
        relative_uncertainty=(0.001, 0.002),
        status="certified",
        source="hypothetical certificate, for the test",
        provenance="test",
        feature_uncertainty_nm=0.2,
        free_axis=None,
    )
    scans = _scans(tile, seed=7, anisotropy=1.0)
    result, _ = calibrate_lateral([s.image for s in scans], certified, bootstrap=50)
    assert result.traceable
    assert not result.anisotropy_fitted
    assert result.anisotropy.value == 1.0
    assert result.scale_x.value == pytest.approx(1.05, abs=result.scale_x.expanded)
    assert result.scale_y.value == pytest.approx(0.97, abs=result.scale_y.expanded)
    # With the anisotropy fixed, a stretch of the reference along either axis
    # is shared between the scanner's two scales over particles at random
    # angles, about half each: hypot(0.5 x 0.001, 0.5 x 0.002) of sx.
    # Measured 0.00096 against 0.00117.
    assert result.scale_x.u_reference_scale == pytest.approx(
        1.05 * math.hypot(0.0005, 0.001), rel=0.3
    )
    # 0.2 nm per feature, the same on every particle, is 0.2% of scale
    # (measured 0.0021): a per-feature systematic does not average away.
    assert result.scale_x.u_reference_features > 0.001


# --- negative controls -----------------------------------------------------------


def test_particles_at_one_angle_cannot_separate_scanner_from_object(
    tile: CalibrationTile, reference: ReferenceGeometry
) -> None:
    scans = _scans(tile, seed=2, angles_deg=(30.0, 33.0))
    with pytest.raises(CalibrationRefused, match="too alike"):
        calibrate_lateral([s.image for s in scans], reference, bootstrap=10)
    # Fixing the anisotropy is the documented way out, and it then fits.
    result, _ = calibrate_lateral(
        [s.image for s in scans], reference, fit_anisotropy=False, bootstrap=10
    )
    assert not result.anisotropy_fitted


def test_too_few_particles_are_refused(tile: CalibrationTile, reference: ReferenceGeometry) -> None:
    scan = calibration_scan(tile.marks_nm, sheet_nm=tile.sheet_nm, n_tiles=6, seed=4, **TRUTH)
    with pytest.raises(CalibrationRefused, match="at least 10"):
        calibrate_lateral([scan.image], reference)


def test_plain_rectangles_match_nothing(
    tile: CalibrationTile, reference: ReferenceGeometry
) -> None:
    scan = calibration_scan([], sheet_nm=tile.sheet_nm, n_tiles=16, seed=5, **TRUTH)
    detection = detect(scan.image, reference)
    assert detection.matches == ()
    assert detection.rejected == {"no_marks": len(scan.truth)}
    with pytest.raises(CalibrationRefused, match="no particle matched the reference"):
        calibrate_lateral([scan.image], reference)


def test_face_down_tiles_are_left_out_and_counted(
    tile: CalibrationTile, reference: ReferenceGeometry
) -> None:
    scan = calibration_scan(
        tile.marks_nm,
        sheet_nm=tile.sheet_nm,
        n_tiles=20,
        face_down_fraction=0.4,
        missing_fraction=0.05,
        seed=6,
        **TRUTH,
    )
    down = sum(t.shows == "none" for t in scan.truth)
    detection = detect(scan.image, reference)
    assert down > 0
    assert detection.rejected.get("no_marks", 0) == down
    assert len(detection.matches) >= len(scan.truth) - down - 1
    # Both handednesses come through the matcher: mirrored landings are used.
    assert {m.handedness for m in detection.matches} == {-1, 1}


def test_a_symmetric_reference_is_ambiguous_and_rejected(
    tile: CalibrationTile, reference: ReferenceGeometry
) -> None:
    """The four corner marks alone read the same turned by a half turn: every
    particle must be rejected as ambiguous, never fitted either way."""
    corners = ReferenceGeometry(
        name="corners only",
        features=tuple(f for f in reference.features if f.name in {"c1r0", "c8r0", "c1r4", "c8r4"}),
        relative_uncertainty=reference.relative_uncertainty,
        status="nominal",
        provenance="test",
        free_axis="y",
    )
    scan = calibration_scan(tile.marks_nm, sheet_nm=tile.sheet_nm, n_tiles=8, seed=8, **TRUTH)
    detection = detect(scan.image, corners)
    assert detection.matches == ()
    assert detection.rejected == {"ambiguous": len(scan.truth)}


def test_fit_scanner_refuses_an_empty_list(reference: ReferenceGeometry) -> None:
    with pytest.raises(CalibrationRefused, match="no particle matched"):
        fit_scanner([], reference, rejected={"no_marks": 3})

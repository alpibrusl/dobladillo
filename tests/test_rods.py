"""E10: tracing rods, and telling a straight flexible bundle from a curved one.

Everything here runs against shapes and images whose answer we chose. The
negative controls are the point: a population of rods with a built-in arc must
be called curved, a straight one of the same stiffness must not, and the
estimate of the persistence length must cover the value the rods were drawn
from.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.experiments.rods import (
    OLD_ARC_RADII_NM,
    classify_traces,
    cylinder_half_height_broadening_nm,
    predict_rods,
    shape_fit,
)
from dobladillo.imaging import wlc
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.rods import trace_particles
from dobladillo.imaging.synthetic import synthetic_rod_scan

runner = CliRunner()
CONTOUR = 390.4


# ------------------------------------------------------------ the model


def test_end_to_end_limits() -> None:
    """Stiff: R^2 -> L^2. Flexible: R^2 -> 4 Lp L, the 2D random-walk limit."""
    assert wlc.mean_square_end_to_end_2d(100.0, 1e9) == pytest.approx(100.0**2, rel=1e-6)
    assert wlc.mean_square_end_to_end_2d(1e6, 50.0) == pytest.approx(4 * 50.0 * 1e6, rel=1e-3)


def test_sampled_chains_match_the_analytic_end_to_end() -> None:
    """The sampler and the formula were written separately; they must agree."""
    shapes = wlc.sample_shapes(3000, contour_nm=CONTOUR, lp_nm=300.0, seed=1)
    sampled = np.mean([wlc.end_to_end(p) ** 2 for p in shapes])
    assert sampled == pytest.approx(wlc.mean_square_end_to_end_2d(CONTOUR, 300.0), rel=0.03)


def test_arc_geometry() -> None:
    """A half circle: chord 2R over contour pi R, sagitta R."""
    half = wlc.Arc(contour_nm=math.pi * 100.0, radius_nm=100.0)
    assert half.end_to_end_ratio == pytest.approx(2 / math.pi)
    assert half.sagitta_nm == pytest.approx(100.0)
    assert wlc.sagitta(np.array([[0, 0], [1, 1], [2, 0]], dtype=float)) == pytest.approx(1.0)


def test_straight_population_is_not_called_curved_and_lp_is_recovered() -> None:
    shapes = wlc.sample_shapes(120, contour_nm=CONTOUR, lp_nm=1500.0, seed=4)
    angles = [wlc.tangent_angles(wlc.resample(p, 4.0)) for p in shapes]
    fit = wlc.fit_tangent_msd(angles, ds_nm=4.0, s_min_nm=20, s_max_nm=280)
    assert not fit.systematically_curved
    low, high = fit.lp_ci95_nm
    assert low < 1500.0 < high


@pytest.mark.parametrize("radius", OLD_ARC_RADII_NM)
def test_the_old_arcs_are_called_curved(radius: float) -> None:
    shapes = wlc.sample_shapes(
        100, contour_nm=CONTOUR, lp_nm=1500.0, curvature_per_nm=1 / radius, seed=5
    )
    angles = [wlc.tangent_angles(wlc.resample(p, 4.0)) for p in shapes]
    fit = wlc.fit_tangent_msd(angles, ds_nm=4.0, s_min_nm=20, s_max_nm=280)
    assert fit.systematically_curved
    assert 1 / fit.curvature_per_nm == pytest.approx(radius, rel=0.15)


def test_end_to_end_lp_is_dragged_down_by_an_arc() -> None:
    """The cross-check's documented failure, used as a diagnostic."""
    straight = wlc.sample_shapes(200, contour_nm=CONTOUR, lp_nm=1500.0, seed=6)
    curved = wlc.sample_shapes(
        200, contour_nm=CONTOUR, lp_nm=1500.0, curvature_per_nm=1 / 269, seed=6
    )

    def lp(shapes: list[np.ndarray]) -> float:
        return wlc.lp_from_end_to_end(
            [wlc.contour_length(p) for p in shapes], [wlc.end_to_end(p) for p in shapes]
        )["persistence_length_nm"]

    assert lp(straight) == pytest.approx(1500.0, rel=0.25)
    assert lp(curved) < 500.0


def test_the_prediction_separates_straight_from_the_old_arcs() -> None:
    prediction = predict_rods(contour_nm=CONTOUR, diameter_nm=8.0, samples=1000)
    assert prediction == predict_rods(contour_nm=CONTOUR, diameter_nm=8.0, samples=1000)
    stiffest_arc = max(a["end_to_end_ratio"]["median"] for a in prediction["systematic_arc"])
    floppiest_straight = min(
        s["end_to_end_ratio"]["median"] for s in prediction["straight_flexible"]
    )
    assert stiffest_arc < floppiest_straight
    assert all(s["intrinsic_curvature_sq_per_nm2"] == 0 for s in prediction["straight_flexible"])
    assert {
        round(1 / math.sqrt(a["intrinsic_curvature_sq_per_nm2"]))
        for a in prediction["systematic_arc"]
    } == {round(r) for r in OLD_ARC_RADII_NM}


def test_round_rod_broadening() -> None:
    """sqrt(r^2 + 2Rr) - r: 5.8 nm for an 8 nm rod under a 10 nm tip, against the
    plateau model's 8.0 -- the gap that makes the width model-dependent."""
    assert cylinder_half_height_broadening_nm(
        tip_radius_nm=10.0, feature_height_nm=8.0
    ) == pytest.approx(math.sqrt(16 + 80) - 4)
    assert half_height_broadening_nm(tip_radius_nm=10.0, feature_height_nm=8.0) == pytest.approx(
        8.0
    )


# ------------------------------------------------------ images and tracing


def _traces(**kwargs: object) -> list:
    scan = synthetic_rod_scan(**kwargs)  # type: ignore[arg-type]
    flat, background = flatten(scan.image)
    return trace_particles(flat, background)


def test_a_rendered_rod_has_the_round_rod_width() -> None:
    """The fixture's own geometry, checked in closed form before anything relies on it."""
    scan = synthetic_rod_scan(
        size_px=512, scan_nm=512.0, n_rods=1, lp_nm=1e9, noise_nm=0, tilt_nm=0, line_noise_nm=0
    )
    rod = scan.rods[0].points_nm
    middle = rod[len(rod) // 2]
    direction = rod[len(rod) // 2 + 1] - rod[len(rod) // 2 - 1]
    normal = np.array([-direction[1], direction[0]]) / np.linalg.norm(direction)
    from scipy.ndimage import map_coordinates

    offsets = np.linspace(-30, 30, 6001)
    points = middle + offsets[:, None] * normal
    profile = map_coordinates(scan.image.heights_nm, points[:, ::-1].T, order=1)
    above = offsets[profile > 4.0]
    width = above.max() - above.min()
    assert width == pytest.approx(2 * math.sqrt(16 + 80), abs=1.0)


def test_straight_rods_are_traced_to_their_length() -> None:
    traces = _traces(size_px=1024, n_rods=20, lp_nm=1e9, seed=2)
    rods = [t for t in traces if not t.touches_edge]
    assert len(rods) >= 18
    for t in rods:
        corrected = t.contour_nm - 2 * half_height_broadening_nm(
            tip_radius_nm=10.0, feature_height_nm=t.height_nm
        )
        assert corrected == pytest.approx(CONTOUR, rel=0.015)
        assert t.end_to_end_nm / t.contour_nm > 0.998
        assert not t.branched


def test_crossings_are_branched_and_blobs_are_aggregates() -> None:
    traces = [
        t
        for t in _traces(
            size_px=1024, n_rods=6, n_crossings=2, n_aggregates=2, n_fragments=2, seed=3
        )
        if not t.touches_edge
    ]
    classes, _ = classify_traces(traces, contour_nm=CONTOUR, tip_radius_nm=10.0)
    assert classes.count("branched") == 2
    assert classes.count("aggregate") == 2
    assert classes.count("short") == 2
    assert classes.count("rod") == 6


@pytest.fixture(scope="module")
def populations() -> dict[str, list]:
    """Three scans each: straight and flexible, and curved like the old routing."""
    found = {}
    for name, curvature in (("straight", 0.0), ("curved", 1 / 269)):
        traces = []
        for seed in (11, 12, 13):
            traces += _traces(
                size_px=512, n_rods=30, lp_nm=1500.0, curvature_per_nm=curvature, seed=seed
            )
        found[name] = [
            t for t in traces if not t.touches_edge and not t.branched and t.contour_nm > 300
        ]
    return found


def test_image_straight_population_passes(populations: dict[str, list]) -> None:
    fit, end_to_end = shape_fit(populations["straight"])
    assert len(populations["straight"]) >= 80
    assert not fit.systematically_curved
    assert fit.curvature_ci95_per_nm[1] < 1 / max(OLD_ARC_RADII_NM), "old arcs excluded"
    low, high = fit.lp_ci95_nm
    assert low < 1500.0 < high
    e_low, e_high = end_to_end["persistence_length_ci95_nm"]
    assert e_low < 1500.0 < e_high


def test_image_curved_population_is_caught(populations: dict[str, list]) -> None:
    """The negative control: the old defect, rendered and traced, must be found."""
    fit, end_to_end = shape_fit(populations["curved"])
    assert fit.systematically_curved
    assert 1 / fit.curvature_per_nm == pytest.approx(269, rel=0.2)
    assert fit.curvature_ci95_per_nm[0] > 1 / 1000, "and not mistaken for a gentle bow"
    # And the cross-check disagrees with the tangent fit, as it should on an arc.
    assert end_to_end["persistence_length_nm"] < 0.5 * fit.lp_nm


# ------------------------------------------------------------------ CLI


def _folder(tmp_path: Path) -> Path:
    result = runner.invoke(
        app, ["experiment", "new", "2026-09-28-bundle", "--part", "bundle", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    return tmp_path / "2026-09-28-bundle"


def test_experiment_new_records_the_rod_prediction_and_the_published_protocol(
    tmp_path: Path,
) -> None:
    folder = _folder(tmp_path)
    prediction = json.loads((folder / "pre" / "prediction.json").read_text())
    assert prediction["predicted_nm"]["height"] == pytest.approx(8.0)
    assert "straight_flexible" in prediction["rods"]
    protocol = (folder / "pre" / "protocol.md").read_text()
    assert "10.1039/D4NR02185A" in protocol
    assert "12.5 mM MgCl2" in protocol
    # Nothing of the generic sheet leaks in: it is a different protocol.
    assert "Tris, 1.0 mM EDTA" not in protocol


def test_rods_refuses_without_a_measured_tip(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    result = runner.invoke(app, ["experiment", "rods", str(folder), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["kind"] == "no_tip_radius"


def test_rods_refuses_without_a_prediction(tmp_path: Path) -> None:
    (tmp_path / "e" / "during").mkdir(parents=True)
    result = runner.invoke(app, ["experiment", "rods", str(tmp_path / "e"), "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "no_prediction"


def test_rods_end_to_end_on_a_synthetic_folder(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    instrument = folder / "during" / "instrument.json"
    record = json.loads(instrument.read_text())
    # The rendered tip, not a measurement: this folder is a fixture.
    record["tip"]["measured_radius_before_nm"] = 10.0
    record["tip"]["measured_radius_after_nm"] = 10.0
    instrument.write_text(json.dumps(record))
    for seed in (21, 22):
        out = folder / "during" / "raw" / f"scan-{seed}.gsf"
        made = runner.invoke(
            app,
            [
                "afm",
                "synthetic",
                "--part",
                "bundle",
                "--seed",
                str(seed),
                "--rectangles",
                "25",
                "--out",
                str(out),
            ],
        )
        assert made.exit_code == 0, made.output
    result = runner.invoke(app, ["experiment", "rods", str(folder), "--json"])
    # 50 rods is below the 100 the command asks for, so it says so and exits 1.
    assert result.exit_code == 1
    rods = json.loads(result.stdout)
    assert rods["too_few_rods"]
    assert rods["prediction_preregistered"]
    assert rods["contour"]["agrees"]
    assert not rods["tangent_fit"]["systematically_curved"]
    assert (folder / "post" / "rods.json").is_file()


def test_the_published_protocol_says_where_every_value_came_from() -> None:
    """A value with no quote and no note is a number from memory."""
    from dobladillo.lab.published import BUNDLE_ENLUND_2024, NOT_STATED

    protocol = BUNDLE_ENLUND_2024
    steps = (
        protocol.fold + protocol.anneal + protocol.gel + protocol.purification + protocol.deposition
    )
    for step in steps:
        if step.stated:
            assert step.quote or step.note, step.what
    assert any(not s.stated for s in steps), "unstated parameters are recorded, not filled"
    assert NOT_STATED in protocol.markdown()

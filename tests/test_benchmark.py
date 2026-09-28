"""The known-answer benchmark (#14), run in full, and shown able to fail.

A benchmark that cannot fail is decoration. So besides running it, each way
it could go blind is seeded here -- a phasing ceiling relaxed, a predictor
with the wrong stiffness, a known-bad design expected to pass, a known failure
that quietly starts passing -- and each must turn the run red.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from dobladillo import benchmark
from dobladillo.cli import app

DATA = Path(__file__).parent / "data"
runner = CliRunner()


@pytest.fixture(scope="module")
def full() -> dict[str, Any]:
    """The whole benchmark, once, through the CLI an agent would use."""
    result = runner.invoke(app, ["benchmark", "--json"])
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def _case(payload: dict[str, Any], case_id: str) -> dict[str, Any]:
    found = [c for c in payload["cases"] if c["id"] == case_id]
    assert len(found) == 1, case_id
    return found[0]


def test_the_benchmark_passes_at_head(full: dict[str, Any]) -> None:
    assert full["ok"] is True
    assert full["counts"]["fail"] == 0
    assert full["counts"]["unexpected_pass"] == 0
    assert full["counts"]["pass"] >= 20


def test_every_published_design_passes_phasing(full: dict[str, Any]) -> None:
    published = [
        c
        for c in full["cases"]
        if c["check"] in ("phasing", "placement")
        and c["design"].startswith(("reference_designs/", "published_shapes/"))
    ]
    assert len(published) == 6
    assert all(c["status"] == "pass" and c["observed"]["acceptable"] for c in published)


@pytest.mark.parametrize("bundle", ["bundle-21-21", "bundle-28-14"])
def test_the_bundles_oxdna_showed_bent_are_rejected(full: dict[str, Any], bundle: str) -> None:
    """The negative control the issue asks for: designs known bad, rejected
    by phasing, by lint, and by `predict`'s own validity check."""
    assert _case(full, f"phasing/{bundle}")["observed"]["acceptable"] is False
    assert _case(full, f"lint/{bundle}")["observed"]["hard_by_rule"]["crossover_azimuth"] > 0
    assert _case(full, f"validity/{bundle}")["observed"]["valid"] is False
    for prefix in ("phasing", "lint", "validity"):
        assert _case(full, f"{prefix}/{bundle}")["status"] == "pass"


def test_the_current_bundle_passes(full: dict[str, Any]) -> None:
    """Re-tiled on scadnano's published unit, it is the known-good case now."""
    for prefix in ("phasing", "lint", "validity"):
        case = _case(full, f"{prefix}/bundle-current")
        assert case["expect"] == "pass"
        assert case["status"] == "pass"


def test_the_composite_beam_is_reproduced(full: dict[str, Any]) -> None:
    observed = _case(full, "shape/composite-beam-6hb")["observed"]
    assert observed["expected_radius_nm"] == pytest.approx(168.0, abs=0.05)
    assert observed["radius_nm"] == pytest.approx(168.0, rel=0.01)


def test_the_dietz_bend_is_reported_as_a_known_failure(full: dict[str, Any]) -> None:
    """Pinned so the finding cannot be lost: the default model under-bends
    Dietz 2009's 120 deg bundle, and the coupling term is what moves it."""
    case = _case(full, "shape/dietz09-bend-120")
    assert case["status"] == "known_failure"
    observed = case["observed"]
    assert observed["measured_deg"] == 121.0
    assert observed["predicted_deg"] < observed["measured_deg"] - 2 * observed["measured_sd_deg"]
    assert abs(observed["predicted_without_twist_stretch_coupling_deg"] - 121.0) < 2 * 8.4


def test_rule_conflicts_with_published_designs_are_flagged(full: dict[str, Any]) -> None:
    """AGENTS.md rule 8: flag, do not silently relax."""
    for design in ("nature09-monolith", "nature09-squarenut", "dietz09-bend-120"):
        case = _case(full, f"lint/{design}")
        assert case["status"] == "known_failure"
        assert "AGENTS.md rule 8" in case["known_failure"]


def test_what_is_missing_is_reported(full: dict[str, Any]) -> None:
    wanted = {w["id"] for w in full["wanted"]}
    assert {"shape/dietz09-bend-series", "shape/dietz09-twisted-ribbons"} <= wanted
    assert all(w["why_not"] for w in full["wanted"])


def test_every_case_cites_a_source() -> None:
    manifest = json.loads((DATA / "known_answers.json").read_text())
    assert all(len(c["source"]) > 20 for c in manifest["cases"])


def test_the_published_curved_design_is_the_file_that_was_checked() -> None:
    blob = (DATA / "published_shapes" / "Science09_prot120_98_v3.json").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == (
        "9659444180251d480bd11aa7f24ffbf52dbd020433a3bfed470903a00b5255b6"
    )


# ------------------------------------------------------ it can fail


def _manifest(tmp_path: Path, cases: list[dict[str, Any]]) -> Path:
    path = tmp_path / "known_answers.json"
    path.write_text(json.dumps({"schema": 1, "cases": cases, "wanted": []}))
    return path


def _phasing_case(design: str, expect: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"phasing/{Path(design).stem}",
        "stage": "routing",
        "check": "phasing",
        "design": str(DATA / design),
        "expect": expect,
        "source": "seeded by tests/test_benchmark.py",
        **extra,
    }


def test_a_known_bad_design_expected_to_pass_fails_the_run(tmp_path: Path) -> None:
    path = _manifest(tmp_path, [_phasing_case("our_designs/bundle_21_21.sc", "pass")])
    report = benchmark.run(path)
    assert not report.ok
    assert [c.status for c in report.cases] == ["fail"]

    result = runner.invoke(app, ["benchmark", "--manifest", str(path), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["ok"] is False


def test_a_relaxed_phasing_ceiling_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """If someone raises the rms ceiling past the 28/14 bundle's 44 deg,
    the design oxDNA showed bent would pass. The benchmark must say so."""
    from dobladillo.routing import azimuth

    monkeypatch.setattr(azimuth, "MAX_RMS_DEG", 60.0)
    report = benchmark.run(only=["phasing/bundle-28-14"])
    assert [c.status for c in report.cases] == ["fail"]


def test_a_predictor_with_the_wrong_stiffness_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from dobladillo.mechanics import beam

    original = beam.predict

    def stiffer(design: Any, parameters: Any = None) -> Any:
        p = parameters or beam.BeamParameters()
        return original(design, dataclasses.replace(p, bend_pn_nm2=2 * p.bend_pn_nm2))

    monkeypatch.setattr(beam, "predict", stiffer)
    report = benchmark.run(only=["shape/composite-beam-6hb"])
    assert [c.status for c in report.cases] == ["fail"]


def test_a_known_failure_that_starts_passing_fails_the_run(tmp_path: Path) -> None:
    """As xfail(strict=True): the manifest must be updated by a person."""
    case = _phasing_case(
        "reference_designs/6_helix_bundle_honeycomb.sc", "pass", known_failure="seeded"
    )
    report = benchmark.run(_manifest(tmp_path, [case]))
    assert [c.status for c in report.cases] == ["unexpected_pass"]
    assert not report.ok


def test_the_measure_is_restored_after_a_run() -> None:
    from dobladillo.routing import azimuth

    before = azimuth.measure
    benchmark.run(only=["phasing/bundle-21-21"])
    assert azimuth.measure is before


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        ({"source": ""}, "lacks source"),
        ({"check": "vibes"}, "unknown check"),
    ],
)
def test_a_case_without_provenance_is_refused(
    tmp_path: Path, broken: dict[str, Any], message: str
) -> None:
    case = {**_phasing_case("our_designs/bundle_21_21.sc", "fail"), **broken}
    with pytest.raises(ValueError, match=message):
        benchmark.run(_manifest(tmp_path, [case]))


def test_a_wanted_entry_must_say_why_it_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"cases": [], "wanted": [{"id": "x", "what": "y"}]}))
    with pytest.raises(ValueError, match="does not say why"):
        benchmark.load_manifest(path)


def test_cli_refuses_an_unknown_case_prefix() -> None:
    result = runner.invoke(app, ["benchmark", "--case", "no-such/", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["kind"] == "bad_manifest"


# ------------------------------------------------------ the helpers


def test_bend_angle_matches_length_over_radius_for_uniform_curvature() -> None:
    """For a uniformly curved beam the angle between the ends is L / R. The
    composite-beam case is uniform over its length, so the two measures of
    the same solve must agree -- an independent check on `bend_angle_deg`."""
    import math

    from dobladillo.mechanics.beam import BeamParameters, predict

    p = BeamParameters(twist_stretch_pn_nm=0.0)
    design = benchmark.one_helix_shortened()
    shape = predict(design, p)
    angle = benchmark.bend_angle_deg(design, p)
    assert angle == pytest.approx(math.degrees(shape.length_nm / shape.radius_nm), rel=0.03)


def test_a_straight_design_has_no_bend_angle() -> None:
    from dobladillo.parts.bundle import six_helix_bundle

    assert benchmark.bend_angle_deg(six_helix_bundle().design) < 0.5


def test_dropping_a_helix_keeps_every_other_base() -> None:
    """Helix 19 of the Dietz file parks the leftover scaffold; removing it
    must remove exactly its bases and nothing else."""
    design = benchmark.load_design("published_shapes/Science09_prot120_98_v3.json", DATA)

    def bases(d: Any, *, on_19: bool) -> int:
        return sum(
            dom.dna_length()
            for s in d.strands
            for dom in s.domains
            if hasattr(dom, "helix") and (dom.helix == 19) == on_19
        )

    trimmed = benchmark.without_helices(design, {19})
    assert 19 not in trimmed.helices
    assert bases(trimmed, on_19=True) == 0
    assert bases(trimmed, on_19=False) == bases(design, on_19=False)

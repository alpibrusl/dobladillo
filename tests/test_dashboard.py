"""The dashboard is generated, so the test is that it cannot drift."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo.cli import app
from dobladillo.dashboard import gather, render
from dobladillo.programme import EXPERIMENTS, by_id, critical_path

runner = CliRunner()


@pytest.fixture(scope="module")
def state():
    return gather(experiments_root=Path("experiments"))


@pytest.fixture(scope="module")
def page(state):
    return render(state)


def test_scores_are_in_range() -> None:
    """The dataclass validates, so this is really a test that every entry went
    through it rather than being appended to a list of tuples."""
    for experiment in EXPERIMENTS:
        assert 1 <= experiment.relevance <= 5
        assert 1 <= experiment.difficulty <= 5
        assert 0 < experiment.success <= 1


def test_a_score_outside_its_range_is_refused() -> None:
    from dobladillo.programme import Experiment

    with pytest.raises(ValueError, match="relevance is 1..5"):
        Experiment(
            id="X",
            title="t",
            epic=None,
            relevance=9,
            difficulty=1,
            success=0.5,
            blocked_by="",
            why="w",
        )
    with pytest.raises(ValueError, match="probability"):
        Experiment(
            id="X",
            title="t",
            epic=None,
            relevance=1,
            difficulty=1,
            success=1.5,
            blocked_by="",
            why="w",
        )


def test_every_experiment_says_why_it_matters() -> None:
    """A score with no rationale is unfalsifiable and reads as a calculation."""
    for experiment in EXPERIMENTS:
        assert len(experiment.why) > 80, experiment.id


def test_the_prose_roadmap_lists_the_same_experiments() -> None:
    """Two sources, and this is the only thing stopping them diverging.
    `experiments/ROADMAP.md` is prose for a person; `programme.py` is the same
    programme as data. If an experiment is added to one and not the other, the
    dashboard and the document disagree and neither says so."""
    text = Path("experiments/ROADMAP.md").read_text()
    for experiment in EXPERIMENTS:
        assert re.search(rf"\b{experiment.id}\b", text), f"{experiment.id} missing from ROADMAP.md"


def test_critical_path_is_a_product_of_its_members(state) -> None:
    chain, product = critical_path()
    expected = 1.0
    for experiment in chain:
        expected *= experiment.success
    assert product == pytest.approx(expected)
    assert all(by_id(i).on_critical_path for i in state.critical_path)


def test_the_page_reports_lint_state_as_it_finds_it(state, page) -> None:
    """The reason this is generated rather than written. Within one day the
    bundle went clean, then failed a new rule, then was fixed. A hand-written
    page would have been wrong twice; this one is only ever as wrong as the
    linter.

    So the assertion is on agreement with the linter, not on a verdict.
    """
    from dobladillo.routing.rules import Severity, lint

    for part in state.parts:
        builders = {"rectangle": "rectangle", "bundle": "bundle", "hinge": "hinge"}
        assert part.name in builders
        if part.clean:
            assert "clean" in page
        else:
            assert part.worst in page

    from dobladillo.parts.bundle import six_helix_bundle

    live = [
        v for v in lint(six_helix_bundle().design).violations if v.severity is Severity.VIOLATION
    ]
    shown = next(p for p in state.parts if p.name == "bundle")
    assert shown.violations == len(live)


def test_the_page_carries_its_own_state_as_json(page) -> None:
    """So anything reading the page does not have to parse the presentation."""
    blob = re.search(r'<script id="state" type="application/json">(.*?)</script>', page, re.S)
    assert blob
    payload = json.loads(blob.group(1))
    assert len(payload["experiments"]) == len(EXPERIMENTS)
    assert payload["programme_cost"]["total_eur"] > 0


def test_costs_come_from_the_cost_model_not_from_the_page(state) -> None:
    from dobladillo.hamiltonian import experiments as series

    expected = series.programme_cost_eur(series.all_series())
    assert state.programme_cost == expected


def test_tip_corrections_come_from_the_geometry(state) -> None:
    from dobladillo.compare.corrections import half_height_broadening_nm

    entry = next(e for e in state.tip_table if e["radius_nm"] == 10.0)
    expected = 2 * half_height_broadening_nm(tip_radius_nm=10.0, feature_height_nm=2.0)
    assert entry["widening_nm"][2.0] == pytest.approx(expected, abs=0.05)


def test_every_theme_colour_is_defined_outside_a_media_query(page) -> None:
    """The classic artifact bug: a colour whose only definition sits behind
    prefers-color-scheme renders one theme's text on the other theme's ground."""
    base = re.search(r":root\{(.*?)\}", page, re.S)
    assert base
    declared = set(re.findall(r"(--[a-z-]+):", base.group(1)))
    used = set(re.findall(r"var\((--[a-z-]+)\)", page))
    assert used <= declared, f"used but never defined on bare :root: {sorted(used - declared)}"


def test_the_cli_writes_a_page_and_reports_what_it_found(tmp_path: Path) -> None:
    result = runner.invoke(app, ["dashboard", "--out", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    written = Path(payload["file"])
    assert written.is_file()
    assert written.read_text().startswith("<!doctype html>")
    # as_dict rounds to four places for the embedded JSON; compare at that
    # precision rather than loosening the round trip elsewhere.
    assert payload["critical_probability"] == pytest.approx(critical_path()[1], abs=5e-5)


def test_a_missing_experiments_directory_is_not_an_error(tmp_path: Path) -> None:
    """The page is also generated from a fresh clone."""
    fresh = gather(experiments_root=tmp_path / "nope")
    assert fresh.folders == []
    assert "No experiment folders yet" in render(fresh)

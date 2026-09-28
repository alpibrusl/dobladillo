"""The folding window: staple melting temperatures that point E11's screen.

Checked for the properties that must hold whatever the model's absolute
accuracy: more magnesium raises every melting temperature; a staple with a
short strongest domain melts lower and is flagged; the screen brackets the
bulk of the distribution. The absolute position is E11's to measure.
"""

from __future__ import annotations

import pytest

from dobladillo.parts.rectangle import rothemund_rectangle
from dobladillo.sequence.folding import (
    MIN_DOMAIN_FOR_TM_NT,
    domain_melting_c,
    folding_window,
)


@pytest.fixture(scope="module")
def rectangle():
    return rothemund_rectangle()


def test_more_magnesium_raises_every_staple(rectangle) -> None:
    low = folding_window(rectangle.design, magnesium_mm=6.0)
    high = folding_window(rectangle.design, magnesium_mm=20.0)
    assert all(b.tm_c > a.tm_c for a, b in zip(low.staples, high.staples, strict=True))


def test_more_staple_raises_melting_too() -> None:
    kwargs = {"magnesium_m": 0.012, "scaffold_m": 10e-9}
    assert domain_melting_c("GACTGATCAGTCAGTC", staple_m=500e-9, **kwargs) > domain_melting_c(
        "GACTGATCAGTCAGTC", staple_m=50e-9, **kwargs
    )


def test_a_short_strongest_domain_is_flagged_weak(rectangle) -> None:
    window = folding_window(rectangle.design)
    assert window.weak, "the rectangle's 8-nt-domain edge staples should show up"
    median_domain = sorted(s.strongest_domain_nt for s in window.staples)[len(window.staples) // 2]
    assert all(w.strongest_domain_nt <= median_domain for w in window.weak)
    assert all(w.tm_c < window.window_c[0] for w in window.weak)


def test_the_screen_brackets_the_bulk(rectangle) -> None:
    window = folding_window(rectangle.design)
    low, high = window.screen_c
    assert low < window.window_c[0] < window.median_c < window.window_c[1] < high
    assert low >= 30 and high <= 90  # a range a thermocycler gradient can hold


def test_a_design_without_sequences_is_refused() -> None:
    from dobladillo import _scadnano as ad

    design = ad.new_design(helices=2, max_offset=64, grid="square")
    ad.draw(design, 0, 0).to(64).cross(1, 64).to(0).as_scaffold()
    ad.draw(design, 1, 0).to(32).cross(0, 32).to(0)
    with pytest.raises(ValueError, match="no sequences"):
        folding_window(design)


def test_the_staple_must_be_in_excess() -> None:
    with pytest.raises(ValueError, match="excess"):
        domain_melting_c("GACTGATCAG", magnesium_m=0.012, staple_m=5e-9, scaffold_m=10e-9)


def test_short_domains_are_not_given_a_melting_temperature() -> None:
    assert MIN_DOMAIN_FOR_TM_NT >= 7


# ------------------------------------------------------------ E11's readout


def _screen_folder(tmp_path, rows: list[str]):
    from dobladillo.experiments import scaffold

    directory = scaffold(
        tmp_path,
        slug="e11",
        prediction={"part": "rectangle", "folding_window": {"staple_tm_c": {"median": 54.0}}},
        plan="# p\n",
        protocol="# p\n",
    )
    (directory / "during" / "gel_quant.csv").write_text(
        "time_min,temperature_c,folded_band,reference_band\n" + "\n".join(rows) + "\n"
    )
    return directory


def test_the_screen_finds_the_fastest_good_fold(tmp_path) -> None:
    from dobladillo.experiments.folding_screen import read_quantification, summarise

    rows = [
        "5,48,300,1000", "5,54,600,1000", "5,60,200,1000",
        "15,48,500,1000", "15,54,900,1000", "15,60,400,1000",
        "60,48,850,1000", "60,54,950,1000", "60,60,700,1000",
    ]  # fmt: skip
    directory = _screen_folder(tmp_path, rows)
    result = summarise(read_quantification(directory), {"staple_tm_c": {"median": 54.0}})
    assert result["by_time"][0]["best_temperature_c"] == 54
    assert result["fastest_good_fold"] == {
        "time_min": 15.0,
        "temperatures_c": [54.0, 54.0],
        "best_temperature_c": 54.0,
    }
    assert result["measured_minus_predicted_median_c"] == 0.0


def test_a_screen_without_its_numbers_is_refused(tmp_path) -> None:
    from typer.testing import CliRunner

    from dobladillo.cli import app

    directory = _screen_folder(tmp_path, ["5,48,300,0"])
    result = CliRunner().invoke(app, ["experiment", "folding-screen", str(directory), "--json"])
    assert result.exit_code != 0
    import json

    assert json.loads(result.stdout)["error"]["kind"] == "bad_quantification"
    (directory / "during" / "gel_quant.csv").unlink()
    result = CliRunner().invoke(app, ["experiment", "folding-screen", str(directory), "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "no_quantification"


def test_experiment_new_records_the_predicted_window(tmp_path) -> None:
    import json

    from typer.testing import CliRunner

    from dobladillo.cli import app

    result = CliRunner().invoke(
        app, ["experiment", "new", "2026-10-01-e11", "--root", str(tmp_path), "--json"]
    )
    assert result.exit_code == 0, result.output
    prediction = json.loads((tmp_path / "2026-10-01-e11" / "pre" / "prediction.json").read_text())
    assert prediction["folding_window"]["staple_tm_c"]["median"] > 40

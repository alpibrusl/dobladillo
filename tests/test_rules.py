"""Each rule is proved twice: it stays quiet on a good design, and it fires on
a design built to break exactly that rule.

A checker that never fires is indistinguishable from one that always passes,
which is why the seeded designs matter more than the clean ones. Each helper
below breaks one rule and nothing else, so a test that fires tells you which
check did the work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scadnano as sc

from dobladillo import _scadnano as ad
from dobladillo.parts.bundle import six_helix_bundle
from dobladillo.parts.rectangle import rothemund_rectangle
from dobladillo.routing.rules import RULES, Severity, lint


def _bare_design(helices: int = 4, max_offset: int = 200) -> sc.Design:
    """A scaffold rastering across `helices` helices, waiting for staples.

    The scaffold runs forward on even helices and backward on odd ones, so a
    seeded staple must do the opposite on each: scadnano refuses two domains
    that overlap on a helix in the same direction, and a staple parallel to the
    scaffold is not a staple anyway.
    """
    design = ad.new_design(helices=helices, max_offset=max_offset, grid="square")
    builder = ad.draw(design, 0, 0).to(max_offset)
    for helix in range(1, helices):
        if helix % 2 == 0:
            builder = builder.cross(helix, 0).to(max_offset)
        else:
            builder = builder.cross(helix, max_offset).to(0)
    builder.as_scaffold()
    return design


def _staple_forward_helix(helix: int) -> bool:
    """Staples oppose the scaffold, which runs forward on even helices."""
    return helix % 2 == 1


def _fired(design: sc.Design, rule: str) -> bool:
    return any(v.rule == rule for v in lint(design, only=[rule]).violations)


# ------------------------------------------------------- the good designs


@pytest.mark.parametrize(
    "part",
    [
        pytest.param(rothemund_rectangle, id="rectangle"),
        pytest.param(
            six_helix_bundle,
            id="bundle",
            marks=pytest.mark.xfail(
                strict=True,
                reason="bundle routing still misphased: 44 deg rms against 20-22 for "
                "published honeycomb designs (crossover_azimuth); see docs/STATUS.md",
            ),
        ),
    ],
)
def test_reference_parts_have_no_hard_violations(part) -> None:
    """The parts this project generates must satisfy their own rules.

    It has caught real defects: the first rectangle put a staple crossover on
    the scaffold's turn, and every square part put half its crossovers on the
    wrong face. The bundle is marked as a known failure rather than dropped,
    so that fixing it is what turns this test green.
    """
    report = lint(part().design)
    assert report.ok, [v.as_dict() for v in report.hard]


def test_warnings_do_not_fail_a_design() -> None:
    """Staples outside the target band are a preference, not a fault."""
    report = lint(rothemund_rectangle().design)
    assert report.warnings
    assert report.ok


# ------------------------------------------------------- the seeded designs


def test_staple_length_fires_on_a_short_staple() -> None:
    design = _bare_design()
    ad.draw(design, 0, 10).to(0)  # 10 nt, under the 20 nt floor
    assert _fired(design, "staple_length")


def test_staple_length_only_warns_outside_the_target_band() -> None:
    design = _bare_design()
    ad.draw(design, 0, 25).to(0)  # legal, but under the 32 nt preference
    found = lint(design, only=["staple_length"]).violations
    assert [v.severity for v in found] == [Severity.WARNING]


def test_seed_domain_fires_when_no_domain_can_nucleate() -> None:
    design = _bare_design()
    # 8 + 8 + 8 across three helices: long enough overall, nothing to hold on
    # with. Three helices rather than two so no helix is revisited.
    ad.draw(design, 0, 8).to(0).cross(1, 0).to(8).cross(2, 8).to(0)
    assert _fired(design, "seed_domain")


def test_min_domain_fires_on_a_stub() -> None:
    design = _bare_design()
    ad.draw(design, 0, 3).to(0).cross(1, 0).to(30)  # a 3 nt stub, then a long grip
    assert _fired(design, "min_domain")


def test_sandwich_fires_on_short_long_short() -> None:
    design = _bare_design()
    ad.draw(design, 0, 6).to(0).cross(1, 0).to(20).cross(2, 20).to(14)
    assert _fired(design, "sandwich")


def test_sandwich_stays_quiet_on_an_even_three_domain_staple() -> None:
    """Three domains are not the problem; two weak ends are."""
    design = _bare_design()
    ad.draw(design, 0, 16).to(0).cross(1, 0).to(16).cross(2, 16).to(0)
    assert not _fired(design, "sandwich")


def test_crossover_clearance_fires_next_to_a_scaffold_crossover() -> None:
    design = _bare_design(max_offset=200)
    # The scaffold turns between helices 0 and 1 at offset 199. A staple
    # starting forward on helix 1 hands over at 198, one base away.
    ad.draw(design, 1, 185).to(199).cross(0, 199).to(185)
    assert _fired(design, "crossover_clearance")


def test_crossover_clearance_ignores_an_unrelated_helix_pair() -> None:
    """Two crossovers at the same offset on different helices are not close."""
    design = ad.new_design(helices=4, max_offset=200, grid="square")
    ad.draw(design, 0, 0).to(200).cross(1, 200).to(0).as_scaffold()
    # Helices 2 and 3 carry no scaffold at all, so nothing to be close to.
    ad.draw(design, 3, 185).to(199).cross(2, 199).to(185)
    assert not _fired(design, "crossover_clearance")


def test_poly_g_fires_on_a_quadruplex_run() -> None:
    design = _bare_design()
    ad.draw(design, 0, 32).to(0).with_sequence("GGGG" + "AT" * 14)
    assert _fired(design, "poly_g")


# ------------------------------------------------------------- the machinery


def test_every_rule_has_a_seeded_test() -> None:
    """Guards against adding a rule and forgetting to prove it can fire."""
    import tests.test_rules as this

    tested = {
        name.removeprefix("test_").split("_fires")[0]
        for name in dir(this)
        if name.startswith("test_") and "_fires" in name
    }
    assert {r.name for r in RULES} <= tested


def test_lint_rejects_an_unknown_rule_name() -> None:
    with pytest.raises(ValueError, match="unknown rule"):
        lint(_bare_design(), only=["no_such_rule"])


def test_report_says_what_it_did_not_check() -> None:
    """Silence about an unimplemented check reads as a pass. It must not."""
    report = lint(six_helix_bundle().design).as_dict()
    assert report["not_checked"]
    assert all(entry["why"] for entry in report["not_checked"])


# ---------------------------------------------------------- crossover azimuth

REFERENCES = sorted(
    p
    for p in (Path(__file__).parent / "data" / "reference_designs").iterdir()
    if p.suffix in (".json", ".sc")
)


def _load(path: Path) -> sc.Design:
    if path.suffix == ".json":
        return sc.Design.from_cadnano_v2(json_dict=json.loads(path.read_text()))
    return sc.Design.from_scadnano_file(str(path))


@pytest.mark.parametrize("path", REFERENCES, ids=[p.stem for p in REFERENCES])
def test_crossover_azimuth_passes_every_published_design(path: Path) -> None:
    """The calibration, kept: designs this project did not write must pass.

    A measure checked only against our own designs would share their mistakes.
    """
    hard = [
        v
        for v in lint(_load(path), only=["crossover_azimuth"]).violations
        if v.severity is Severity.VIOLATION
    ]
    assert not hard, [v.as_dict() for v in hard[:5]]


def test_crossover_azimuth_fires_on_a_repeated_partner() -> None:
    """The defect that blocked E1-E3, seeded: crossovers to the SAME neighbour
    16 bp apart, where the backbone has turned a turn and a half.

    Built with the old square tiling, which did exactly this. The hinge still
    uses it; the rectangle no longer does.
    """
    from dobladillo.parts._lattice import add_raster_scaffold, tile_staples

    design = ad.new_design(helices=6, max_offset=128, grid="square")
    add_raster_scaffold(design, helices=6, length=128)
    tile_staples(design, helices=6, start=0, stop=128)

    found = lint(design, only=["crossover_azimuth"]).violations
    located = [v for v in found if v.helix is not None]
    assert located, "the rule no longer catches a repeated partner"
    assert all(v.severity is Severity.VIOLATION for v in located)
    assert any("rms phasing strain" in v.message for v in found)


def test_crossover_azimuth_fires_on_equal_phase_honeycomb() -> None:
    """The bundle's original defect: both neighbours bonded at one phase.

    Equal 21 bp spans put every crossover at one azimuth, which is what bent
    the original bundle into a 269 nm arc in oxDNA.
    """
    design = ad.new_design_at(positions=[(0, 1), (1, 1), (2, 1)], max_offset=84, grid="honeycomb")
    ad.draw(design, 1, 0).to(84).as_scaffold()
    for start_bp in range(0, 84, 42):
        ad.draw(design, 1, start_bp + 21).to(start_bp).cross(0, start_bp).to(start_bp + 21)
        ad.draw(design, 1, start_bp + 42).to(start_bp + 21).cross(2, start_bp + 21).to(
            start_bp + 42
        )
    assert _fired(design, "crossover_azimuth")


def test_uncorrected_twist_is_a_warning_not_a_violation() -> None:
    """E2's control arm carries twist on purpose and must still be orderable."""
    from dobladillo.parts.twist_pair import twist_pair

    found = lint(twist_pair().uncorrected.design, only=["crossover_azimuth"]).violations
    assert [v.severity for v in found] == [Severity.WARNING]
    assert "uncorrected twist" in found[0].message

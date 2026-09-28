"""The CLI is exercised by invoking it, not by importing it.

A typer app can import cleanly and still be unusable: with a single command and
no callback, typer collapses it into the root command and `dobladillo version`
fails on an unexpected argument. Only a real invocation catches that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo import __version__
from dobladillo.cli import app

runner = CliRunner()


def test_version_is_a_subcommand() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_bare_invocation_shows_help_instead_of_failing() -> None:
    result = runner.invoke(app, [])
    assert "Usage" in result.stdout


def test_unknown_command_is_an_error() -> None:
    assert runner.invoke(app, ["definitely-not-a-command"]).exit_code != 0


# The --json contract, which is what makes this callable by an agent. Each of
# these is a promise the tool makes; a broken one is silent until something
# downstream chokes on half a banner.


@pytest.mark.parametrize(
    "argv",
    [
        ["version"],
        ["scaffolds"],
        ["geometry"],
        ["describe"],
        ["build", "bundle"],
        ["build", "rectangle"],
        ["rules"],
        ["lab", "protocol", "bundle"],
    ],
)
def test_json_mode_emits_exactly_one_object(argv: list[str]) -> None:
    result = runner.invoke(app, [*argv, "--json"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)


def test_failures_are_json_too_and_exit_non_zero() -> None:
    """An agent must never have to tell a traceback from a result."""
    result = runner.invoke(app, ["build", "rectangle", "--helices", "23", "--json"])
    assert result.exit_code != 0
    error = json.loads(result.stdout)["error"]
    assert error["kind"] == "invalid_parameters"
    assert "even" in error["message"]


def test_describe_lists_every_command_with_its_options() -> None:
    payload = json.loads(runner.invoke(app, ["describe", "--json"]).stdout)
    listed = {c["command"] for c in payload["commands"]}
    assert {"version", "scaffolds", "geometry", "describe", "build bundle"} <= listed
    assert payload["conventions"]["json_flag"]

    bundle = next(c for c in payload["commands"] if c["command"] == "build bundle")
    options = {o["name"] for o in bundle["options"]}
    assert {"length", "scaffold", "out_dir", "as_json"} <= options
    assert all(o["help"] for o in bundle["options"] if o["name"] != "as_json")


def test_describe_stays_true_when_a_command_is_added() -> None:
    """It walks the app rather than restating a hand-written list."""
    payload = json.loads(runner.invoke(app, ["describe", "--json"]).stdout)
    from dobladillo.cli import app as live

    declared = {c.name or c.callback.__name__ for c in live.registered_commands}
    listed = {c["command"] for c in payload["commands"]}
    assert declared <= listed


def test_build_writes_the_three_export_formats(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["build", "bundle", "--out", str(tmp_path), "--name", "b", "--json"]
    )
    assert result.exit_code == 0
    files = json.loads(result.stdout)["files"]
    assert set(files) == {"scadnano", "cadnano_v2", "oxview"}
    for path in files.values():
        assert Path(path).stat().st_size > 0


def test_verify_reports_the_cadnano_roundtrip() -> None:
    result = runner.invoke(app, ["build", "bundle", "--verify", "--json"])
    assert json.loads(result.stdout)["cadnano_v2_roundtrip"] is True


def test_lint_passes_a_clean_design_and_exits_zero(tmp_path: Path) -> None:
    """The rectangle, not the bundle. The bundle stopped being a clean design
    when `crossover_phase` was added: it bonds both neighbours of every helix
    at one azimuth, which is why it bends. See docs/BUNDLE_BEND.md."""
    runner.invoke(app, ["build", "rectangle", "--out", str(tmp_path), "--name", "b"])
    result = runner.invoke(app, ["lint", str(tmp_path / "b.sc"), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["counts"]["violations"] == 0


def test_lint_does_not_fail_on_warnings_alone(tmp_path: Path) -> None:
    """Warnings are preferences. A lint that failed on them would be turned off."""
    runner.invoke(app, ["build", "rectangle", "--out", str(tmp_path), "--name", "r"])
    result = runner.invoke(app, ["lint", str(tmp_path / "r.sc"), "--json"])
    payload = json.loads(result.stdout)
    assert payload["counts"]["warnings"] > 0
    assert result.exit_code == 0


def test_lint_reports_what_it_did_not_check(tmp_path: Path) -> None:
    runner.invoke(app, ["build", "bundle", "--out", str(tmp_path), "--name", "b"])
    payload = json.loads(runner.invoke(app, ["lint", str(tmp_path / "b.sc"), "--json"]).stdout)
    assert payload["not_checked"]


def test_lint_on_a_missing_file_is_a_clean_error() -> None:
    result = runner.invoke(app, ["lint", "nowhere.sc", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["kind"] == "missing_file"


def test_lint_rejects_an_unknown_rule(tmp_path: Path) -> None:
    runner.invoke(app, ["build", "bundle", "--out", str(tmp_path), "--name", "b"])
    result = runner.invoke(app, ["lint", str(tmp_path / "b.sc"), "--rule", "nope", "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "unknown_rule"


def test_rules_command_lists_every_rule() -> None:
    from dobladillo.routing.rules import RULES

    payload = json.loads(runner.invoke(app, ["rules", "--json"]).stdout)
    assert {r["name"] for r in payload["rules"]} == {r.name for r in RULES}


def test_cli_defaults_match_the_generators() -> None:
    """The CLI must not restate a default. It did once, and went stale."""
    from dobladillo.parts import bundle, rectangle

    payload = json.loads(runner.invoke(app, ["describe", "--json"]).stdout)
    rect = next(c for c in payload["commands"] if c["command"] == "build rectangle")
    options = {o["name"]: o["default"] for o in rect["options"]}
    assert options["helices"] == rectangle.DEFAULT_HELICES
    assert options["length"] == rectangle.DEFAULT_LENGTH

    bund = next(c for c in payload["commands"] if c["command"] == "build bundle")
    assert {o["name"]: o["default"] for o in bund["options"]}["length"] == bundle.DEFAULT_LENGTH


def test_lab_order_validates_what_it_writes(tmp_path: Path) -> None:
    result = runner.invoke(app, ["lab", "order", "bundle", "--out", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["problems"] == []
    assert set(payload["files"]) == {"idt_bulk_csv", "idt_plate_xlsx"}


def test_lab_order_rejects_an_unsupported_plate() -> None:
    result = runner.invoke(app, ["lab", "order", "bundle", "--plate", "48", "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "invalid_parameters"


def test_lab_order_rejects_an_unknown_part() -> None:
    result = runner.invoke(app, ["lab", "order", "triangle", "--json"])
    assert json.loads(result.stdout)["error"]["kind"] == "unknown_part"


def test_lab_protocol_matches_the_lattice(tmp_path: Path) -> None:
    """A square-lattice plate is 2D and folds fast; a honeycomb bundle is 3D."""
    flat = json.loads(runner.invoke(app, ["lab", "protocol", "rectangle", "--json"]).stdout)
    solid = json.loads(runner.invoke(app, ["lab", "protocol", "bundle", "--json"]).stdout)
    assert flat["anneal"]["ramp"]["rate_unit"] == "C/min"
    assert solid["anneal"]["ramp"]["rate_unit"] == "C/h"
    assert solid["anneal"]["total_hours"] > flat["anneal"]["total_hours"]


def test_sim_bundle_says_it_has_not_run(tmp_path: Path) -> None:
    """A generated bundle must never look like a finished simulation."""
    result = runner.invoke(
        app, ["sim", "bundle", "bundle", "--out", str(tmp_path), "--test", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["metadata"]["status"] == "not run"
    assert payload["trapped_pairs"] > 0


def test_sim_bundle_rejects_a_backend_oxdna_does_not_have(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["sim", "bundle", "bundle", "--out", str(tmp_path), "--backend", "OpenCL", "--json"]
    )
    assert json.loads(result.stdout)["error"]["kind"] == "invalid_parameters"


def test_build_pair_writes_both_arms(tmp_path: Path) -> None:
    """One command, because the arms are only evidence together: building them
    separately invites building them at different times from different
    parameters, which is what the experiment must not do."""
    result = runner.invoke(app, ["build", "pair", "--out", str(tmp_path), "--json"])
    assert result.exit_code == 0
    arms = json.loads(result.stdout)["arms"]
    assert set(arms) == {"corrected", "uncorrected"}
    for arm in arms.values():
        assert set(arm["files"]) == {"scadnano", "cadnano_v2", "oxview"}


def test_the_skill_file_lists_every_command() -> None:
    """Generated from the live surface, so it cannot drift from what the tool
    accepts. A hand-written list is stale the day a command is added."""
    skill = runner.invoke(app, ["skill"]).stdout
    listed = json.loads(runner.invoke(app, ["describe", "--json"]).stdout)["commands"]
    for command in listed:
        if command["command"] in ("describe", "version", "skill"):
            continue
        assert f"`dobladillo {command['command']}`" in skill, command["command"]


def test_the_skill_carries_the_working_rules() -> None:
    """A command list alone would let an agent produce numbers from a bundle
    that was never run."""
    skill = runner.invoke(app, ["skill"]).stdout
    assert skill.startswith("---\nname: dobladillo")
    assert "Never present a generated artefact as a result" in skill
    assert "--allow-test-mode" in skill


def test_every_part_name_the_cli_accepts_actually_builds() -> None:
    """lab order and sim bundle take a part name; a name one accepts and the
    other does not is the kind of gap nobody notices until it fails."""
    for part in ("rectangle", "bundle", "twist-corrected", "twist-uncorrected"):
        result = runner.invoke(app, ["lab", "order", part, "--json"])
        assert result.exit_code == 0, part


def test_human_mode_is_not_json() -> None:
    """The two shapes are generated from one structure; neither leaks."""
    result = runner.invoke(app, ["version"])
    assert "dobladillo" in result.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)


def test_the_committed_skill_file_matches_what_the_tool_generates() -> None:
    """SKILL.md is generated from the command surface, so it cannot drift on
    its own -- but a committed copy can, and the committed copy is the one an
    agent reads. Regenerate with `dobladillo skill > SKILL.md`."""
    from pathlib import Path

    from typer.testing import CliRunner

    from dobladillo.cli import app

    committed = Path(__file__).resolve().parent.parent / "SKILL.md"
    result = CliRunner().invoke(app, ["skill"])
    assert result.exit_code == 0
    assert committed.read_text().strip() == result.stdout.strip(), (
        "SKILL.md is stale; run: dobladillo skill > SKILL.md"
    )


def test_afm_measure_requires_a_measured_tip_radius() -> None:
    """No default, for the same reason `compare` has none: a plausible guess
    produces a plausible wrong answer and nothing downstream can tell."""
    result = runner.invoke(app, ["afm", "measure", "nonexistent.gsf"])
    assert result.exit_code != 0
    assert "tip-radius" in result.output or "tip_radius" in result.output


def test_afm_measure_classifies_against_the_image_not_the_object(tmp_path: Path) -> None:
    """The bug this fixes, and it was the most misleading answer available.

    The expected dimensions describe the object; the image shows the object
    plus the tip. Comparing them directly marked every particle malformed, so
    a correct scan of 38 good rectangles reported 0% well formed -- which
    reads as a fold that failed rather than a comparison that was never valid.
    """
    runner.invoke(
        app,
        [
            "afm",
            "synthetic",
            "--out",
            str(tmp_path / "s.gsf"),
            "--part",
            "twist-corrected",
            "--realistic",
            "--seed",
            "9",
        ],
    )
    result = runner.invoke(
        app, ["afm", "measure", str(tmp_path / "s.gsf"), "--tip-radius", "10", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    assert payload["well_formed"]["fraction"] > 0.9
    # The widening is reported rather than silently folded in, and the raw
    # measurement is kept alongside the corrected one.
    assert payload["widening_nm"] == pytest.approx(8.7, abs=0.2)
    assert payload["measured_nm"]["width"] > payload["deconvolved_nm"]["width"]
    assert payload["deconvolved_nm"]["length"] == pytest.approx(191.0, rel=0.05)


def test_a_wrong_tip_radius_moves_the_dimension_not_the_yield(tmp_path: Path) -> None:
    """Which of the two outputs to distrust when the tip is uncharacterised.

    Assuming 30 nm for a 10 nm tip removes 15.4 nm instead of 8.7, and the
    reported width drops 18%. The yield barely moves, because the expectation
    is shifted by the same widening as the measurement and the two errors
    partly cancel inside the tolerance.

    So the classification is the robust output here and the dimension is the
    fragile one -- the opposite of what one might assume, and worth pinning
    rather than discovering later in an argument about a result.
    """
    runner.invoke(
        app,
        [
            "afm",
            "synthetic",
            "--out",
            str(tmp_path / "s.gsf"),
            "--part",
            "twist-corrected",
            "--seed",
            "3",
        ],
    )
    right = json.loads(
        runner.invoke(
            app, ["afm", "measure", str(tmp_path / "s.gsf"), "--tip-radius", "10", "--json"]
        ).stdout
    )
    wrong = json.loads(
        runner.invoke(
            app, ["afm", "measure", str(tmp_path / "s.gsf"), "--tip-radius", "30", "--json"]
        ).stdout
    )
    right_width = right["deconvolved_nm"]["width"]
    wrong_width = wrong["deconvolved_nm"]["width"]
    assert wrong_width < 0.9 * right_width, "a wrong radius must move the dimension"
    # And the yield does not, which is the point of the test.
    assert wrong["well_formed"]["fraction"] == pytest.approx(
        right["well_formed"]["fraction"], abs=0.1
    )


def test_predict_refuses_to_vouch_for_a_misphased_design() -> None:
    """The beam model cannot see misphasing, so `predict` checks phasing
    itself and marks its own answer invalid. An agent reading only the JSON
    must not be able to take a straight 'prediction' for a bent object."""
    bent = runner.invoke(app, ["predict", "tests/data/our_designs/bundle_21_21.sc", "--json"])
    assert bent.exit_code == 0, bent.output
    assert json.loads(bent.output)["valid"] is False

    good = runner.invoke(app, ["predict", "bundle", "--json"])
    payload = json.loads(good.output)
    assert payload["valid"] is True
    assert payload["straight"] is True


def test_sim_warns_when_runs_would_live_in_a_temp_directory(tmp_path: Path) -> None:
    """#16: two sets of results were lost when a session's temp directory was
    cleaned. A run takes hours; writing it where a cleaner can reach it now
    says so, on stderr, so --json output stays parseable."""
    from dobladillo.sim.queue import RUNS_ROOT, temp_root_warning

    assert temp_root_warning(Path("/tmp/somewhere")) is not None
    assert temp_root_warning(tmp_path) is not None  # pytest's own tmp is a temp dir
    assert temp_root_warning(RUNS_ROOT) is None
    assert "tmp" not in str(RUNS_ROOT)

    result = runner.invoke(
        app, ["sim", "bundle", "rectangle", "--out", str(tmp_path / "b"), "--test", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert "temporary directory" in result.stderr
    json.loads(result.stdout)  # the warning did not leak into the JSON

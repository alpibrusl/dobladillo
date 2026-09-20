"""The CLI is exercised by invoking it, not by importing it.

A typer app can import cleanly and still be unusable: with a single command and
no callback, typer collapses it into the root command and `dobladilo version`
fails on an unexpected argument. Only a real invocation catches that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladilo import __version__
from dobladilo.cli import app

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
    from dobladilo.cli import app as live

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
    runner.invoke(app, ["build", "bundle", "--out", str(tmp_path), "--name", "b"])
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
    from dobladilo.routing.rules import RULES

    payload = json.loads(runner.invoke(app, ["rules", "--json"]).stdout)
    assert {r["name"] for r in payload["rules"]} == {r.name for r in RULES}


def test_cli_defaults_match_the_generators() -> None:
    """The CLI must not restate a default. It did once, and went stale."""
    from dobladilo.parts import bundle, rectangle

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
        app, ["sim", "bundle", "bundle", "--out", str(tmp_path), "--backend", "Metal", "--json"]
    )
    assert json.loads(result.stdout)["error"]["kind"] == "invalid_parameters"


def test_human_mode_is_not_json() -> None:
    """The two shapes are generated from one structure; neither leaks."""
    result = runner.invoke(app, ["version"])
    assert "dobladilo" in result.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)

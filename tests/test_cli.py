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


def test_human_mode_is_not_json() -> None:
    """The two shapes are generated from one structure; neither leaks."""
    result = runner.invoke(app, ["version"])
    assert "dobladilo" in result.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)

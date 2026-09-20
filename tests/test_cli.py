"""The CLI is exercised by invoking it, not by importing it.

A typer app can import cleanly and still be unusable: with a single command and
no callback, typer collapses it into the root command and `dobladilo version`
fails on an unexpected argument. Only a real invocation catches that.
"""

from __future__ import annotations

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

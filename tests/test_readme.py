"""The README's facts come from the code, and this fails when they drift."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo import readme
from dobladillo.cli import app

pytest.importorskip("mcp")  # the mcp-tools section is read from the running server

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def test_the_committed_readme_matches_what_the_code_generates() -> None:
    stale = readme.stale_sections(README.read_text())
    assert not stale, f"README is stale in {stale}; run: uv run dobladillo readme"


def test_the_install_line_is_the_one_ci_runs() -> None:
    """Two places saying which extras to install drift apart; make them one."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    sync = re.search(r"run: (uv sync [^\n]+)", ci)
    assert sync, "ci.yml no longer runs uv sync"
    assert sync.group(1) in README.read_text()


def test_usage_shows_required_arguments() -> None:
    table = readme.commands()
    assert "`dobladillo lint DESIGN_FILE`" in table
    assert "`dobladillo calibrate lateral SCANS...`" in table


def test_every_command_and_tool_is_listed() -> None:
    import typer

    from dobladillo.cli import app as cli_app

    table = readme.commands()
    cli = typer.main.get_command(cli_app)
    for name in cli.commands:
        assert f"`dobladillo {name}" in table, name
    assert "`calibrate_tip`" in readme.mcp_tools()


def test_render_refuses_a_readme_without_its_markers() -> None:
    with pytest.raises(ValueError, match="lacks generated sections"):
        readme.render("# a readme with no markers\n")
    with pytest.raises(ValueError, match="does not know"):
        readme.render("<!-- generated:nonsense -->\nx\n<!-- /generated:nonsense -->\n")


def test_check_fails_on_a_stale_copy_and_the_command_fixes_it(tmp_path: Path) -> None:
    copy = tmp_path / "README.md"
    text = README.read_text()
    copy.write_text(text.replace("| `dobladillo lint DESIGN_FILE` |", "| `dobladillo lint` |"))
    runner = CliRunner()
    stale = runner.invoke(app, ["readme", "--check", "--path", str(copy), "--json"])
    assert stale.exit_code == 1
    assert json.loads(stale.stdout)["stale"] == ["commands"]
    fixed = runner.invoke(app, ["readme", "--path", str(copy), "--json"])
    assert fixed.exit_code == 0
    assert copy.read_text() == text

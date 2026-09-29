"""The parts of README.md that code can write, written by code.

A README drifts the moment it restates something the code decides: a command
is added and the list lacks it, an argument becomes required and the example
stops working, an MCP tool is renamed. This one did, twice in a day. So the
facts are generated, the same way `SKILL.md` is, and a test fails when the
committed README differs from what the code says now.

**What is generated, and what is not.** Each generated section sits between
two markers,

    <!-- generated:NAME -->
    ...
    <!-- /generated:NAME -->

and everything outside them is prose a person wrote and may change freely.
The sections:

- `extras`: the optional dependency groups, read from `pyproject.toml`, each
  with its purpose from `EXTRA_PURPOSE`. An extra without a stated purpose is
  an error, so a new one cannot slip in undescribed.
- `commands`: every command, its usage built from its declared arguments, and
  the first line of its docstring, grouped by the command group it lives in.
- `mcp-tools`: every tool the MCP server registers, with the first line of
  its description. Needs the `mcp` extra.
- `mcp-forbidden`: the commands no MCP tool may wrap, and why, from
  `mcp_server.FORBIDDEN_COMMANDS`.

Regenerate with `uv run dobladillo readme`; check with `--check`.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

#: What each optional extra is for. Every extra in pyproject.toml must appear
#: here; `extras()` refuses otherwise.
EXTRA_PURPOSE: Final[dict[str, str]] = {
    "design": "scadnano, the design data model: build, lint, order, simulate",
    "imaging": "read and measure AFM scans; `calibrate`",
    "mcp": "the MCP server (`dobladillo mcp`)",
    "web": "the local web UI for running an experiment (`dobladillo web`), 127.0.0.1 only",
    "dev": "tests, lint, format and type checks",
    "mechanics": "indentation mechanics; declares a private dependency it cannot install",
}

_BLOCK = re.compile(
    r"(<!-- generated:(?P<name>[a-z-]+) -->\n)(?P<body>.*?)(<!-- /generated:(?P=name) -->)",
    re.S,
)


class StaleReadme(ValueError):
    """The README's generated sections do not match the code."""


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def extras() -> str:
    data = tomllib.loads((_root() / "pyproject.toml").read_text())
    groups: dict[str, list[str]] = data["project"].get("optional-dependencies", {})
    missing = sorted(set(groups) - set(EXTRA_PURPOSE))
    if missing:
        raise ValueError(f"extras without a stated purpose in readme.EXTRA_PURPOSE: {missing}")
    rows = ["| extra | for | installs |", "|---|---|---|"]
    for name, packages in groups.items():
        installed = ", ".join(f"`{p}`" for p in packages) or "nothing (see pyproject.toml)"
        rows.append(f"| `{name}` | {EXTRA_PURPOSE[name]} | {installed} |")
    return "\n".join(rows) + "\n"


def _cell(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return text.replace("|", "\\|")


def _usage(path: list[str], command: Any) -> str:
    parts = ["dobladillo", *path]
    for param in command.params:
        # Typer vendors its own click, so isinstance against click.Argument
        # never matches; every click parameter names its own kind.
        if getattr(param, "param_type_name", None) != "argument":
            continue
        name = (param.name or "arg").upper()
        name = f"{name}..." if param.nargs == -1 else name
        parts.append(name if param.required else f"[{name}]")
    return " ".join(parts)


def commands() -> str:
    import typer

    from dobladillo.cli import app

    cli = typer.main.get_command(app)
    groups: dict[str, list[tuple[str, str]]] = {}

    def walk(group: Any, prefix: list[str]) -> None:
        for name, cmd in sorted(group.commands.items()):
            path = [*prefix, name]
            if hasattr(cmd, "commands"):
                walk(cmd, path)
                continue
            text = (cmd.help or "").strip()
            summary = text.splitlines()[0] if text else ""
            heading = prefix[0] if prefix else "(top level)"
            groups.setdefault(heading, []).append((_usage(path, cmd), summary))

    walk(cli, [])
    out: list[str] = []
    for heading in sorted(groups, key=lambda h: (h != "(top level)", h)):
        out.append(f"**{heading}**\n")
        out.append("| command | what it does |")
        out.append("|---|---|")
        for usage, summary in groups[heading]:
            out.append(f"| `{usage}` | {_cell(summary)} |")
        out.append("")
    return "\n".join(out)


def mcp_tools() -> str:
    import anyio

    from dobladillo import mcp_server

    server = mcp_server.create_server(_root() / "experiments")
    tools = anyio.run(server.list_tools)
    rows = ["| tool | what it returns |", "|---|---|"]
    for tool in sorted(tools, key=lambda t: t.name):
        text = " ".join((tool.description or "").split())
        first = re.split(r"(?<=\.)\s", text, maxsplit=1)[0]
        rows.append(f"| `{tool.name}` | {_cell(first)} |")
    return "\n".join(rows) + "\n"


def mcp_forbidden() -> str:
    from dobladillo.mcp_server import FORBIDDEN_COMMANDS

    return "".join(f"- `{c}`: {why}.\n" for c, why in FORBIDDEN_COMMANDS.items())


SECTIONS: Final[dict[str, Callable[[], str]]] = {
    "extras": extras,
    "commands": commands,
    "mcp-tools": mcp_tools,
    "mcp-forbidden": mcp_forbidden,
}


def render(text: str) -> str:
    """`text` with every generated section rewritten from the code."""
    found = {m.group("name") for m in _BLOCK.finditer(text)}
    unknown = found - set(SECTIONS)
    if unknown:
        raise ValueError(f"README has generated sections the code does not know: {sorted(unknown)}")
    missing = set(SECTIONS) - found
    if missing:
        raise ValueError(f"README lacks generated sections: {sorted(missing)}")
    return _BLOCK.sub(lambda m: m.group(1) + SECTIONS[m.group("name")]() + m.group(4), text)


def stale_sections(text: str) -> list[str]:
    """Names of the generated sections whose committed text differs from the code's."""
    current = {m.group("name"): m.group("body") for m in _BLOCK.finditer(text)}
    fresh = {m.group("name"): m.group("body") for m in _BLOCK.finditer(render(text))}
    return sorted(name for name in fresh if current.get(name) != fresh[name])

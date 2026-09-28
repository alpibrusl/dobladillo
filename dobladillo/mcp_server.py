"""An MCP server over the parts, the rules, the simulation queue and the experiments.

The MCP revision of July 2026 separates two things this project had run
together. A **Skill** teaches an agent a task: that is `SKILL.md`, generated
from the command surface and drift-tested. An **MCP server** gives an agent
typed access to a live system. Until now the live systems -- the queue, the
experiment folders -- were reachable only by parsing CLI output.

**One contract, not two.** Every tool here runs the matching CLI command
in-process with `--json` and returns its payload. So a tool cannot say
something the command would not, and a refusal the CLI makes -- a missing
tip radius, a prediction recorded after the data -- reaches the agent as a
structured error carrying the same `kind`. A second implementation of the
same logic would drift from the first, and the refusals are the part that
must not.

**What is deliberately not here.** No tool orders oligos, creates an
experiment, writes a gate, or touches `during/raw/`. Ordering is a purchase,
and creating an experiment is pre-registration, the experimentalist's own
act (`experiments/AGENTS.md`). An agent may analyse, check and report. It
may not pass a human gate, and the absence of a tool is the strongest way to
say so. `test_mcp_server.py` checks that list.

**Nothing may print.** On stdio the server's stdout IS the protocol stream,
so every command runs inside the CLI runner, which captures its output, and
nothing here writes to stdout directly.

**Where it can look.** Experiment folders are addressed by name, relative to
one root, and a name that resolves outside that root is refused. The server
runs on stdio only: it is a local process for a local agent, and the package
never opens a network connection (`tests/test_licences.py`).

Requires the optional `mcp` extra (the official Python SDK, MIT).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Imported at module level on purpose: the SDK evaluates tool annotations at
# registration. This module is only imported when the `mcp` extra is present.
from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult, TextContent

#: Parts the tools accept by name.
PARTS: tuple[str, ...] = ("rectangle", "bundle", "hinge", "twist-corrected", "twist-uncorrected")

#: Commands an agent must never reach through this server, and why. The test
#: asserts no tool wraps any of them.
FORBIDDEN_COMMANDS: dict[str, str] = {
    "lab order": "an oligo order is a purchase, a human gate",
    "experiment new": "creating an experiment is pre-registration, the experimentalist's act",
}


def _run(*args: str) -> tuple[int, dict[str, Any]]:
    """Run a CLI command with --json in-process; return its exit code and payload."""
    from typer.testing import CliRunner

    from dobladillo.cli import app

    result = CliRunner().invoke(app, [*args, "--json"])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "error": {
                "kind": "no_json",
                "message": (result.stdout + (result.stderr or "")).strip()[-2000:]
                or repr(result.exception),
            }
        }
    return result.exit_code, payload


def _answer(code: int, payload: dict[str, Any]) -> CallToolResult:
    """The payload as a tool result; a refusal becomes an MCP error with its `kind`.

    A non-zero exit with a full payload is a verdict, not a refusal: `lint`
    exits 1 on a hard violation and still reports every finding.
    """
    error = payload.get("error")
    refused = isinstance(error, dict) and code != 0
    body = {"error": error} if refused else payload
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(body))],
        structured_content=body,
        is_error=refused,
    )


def create_server(experiments_root: Path) -> MCPServer:
    """Build the server. `experiments_root` bounds every experiment path."""
    root = experiments_root.resolve()
    server = MCPServer(
        name="dobladillo",
        instructions=(
            "DNA origami design, simulation and AFM analysis. Tools return the CLI's "
            "--json payloads. Refusals carry error.kind: do not work around them by "
            "supplying a number an instrument should have measured (see "
            "experiments/AGENTS.md). No tool orders, folds, images or pre-registers."
        ),
    )

    def folder(name: str) -> Path | dict[str, Any]:
        candidate = (root / name).resolve()
        if candidate != root and root not in candidate.parents:
            return {"error": {"kind": "outside_root", "message": f"{name!r} is not under {root}"}}
        if not candidate.is_dir():
            return {"error": {"kind": "missing_folder", "message": f"no experiment {name!r}"}}
        return candidate

    def with_folder(name: str, *command: str) -> CallToolResult:
        found = folder(name)
        if isinstance(found, dict):
            return _answer(2, found)
        return _answer(*_run(*command, str(found)))

    @server.tool()
    def describe() -> CallToolResult:
        """Every CLI command, its options and the conventions of its JSON output."""
        return _answer(*_run("describe"))

    @server.tool()
    def rules() -> CallToolResult:
        """The design rules, and what is knowingly not checked."""
        return _answer(*_run("rules"))

    @server.tool()
    def build_part(part: str) -> CallToolResult:
        """A part's accounting: helices, scaffold, staples, dimensions.

        part: rectangle, bundle or hinge.
        """
        return _answer(*_run("build", part))

    @server.tool()
    def lint_part(part: str) -> CallToolResult:
        """Check a part against every design rule, crossover phasing included.

        part: rectangle, bundle, hinge, twist-corrected or twist-uncorrected.
        """
        import tempfile

        from dobladillo.cli import Emitter, _make_part

        if part not in PARTS:
            return _answer(2, {"error": {"kind": "unknown_part", "message": part}})
        with tempfile.TemporaryDirectory() as tmp:
            # _make_part only prints on an unknown name, excluded above: on
            # stdio, anything printed here would corrupt the protocol stream.
            built = _make_part(part, Emitter(True))
            built.design.write_scadnano_file(directory=tmp, filename=f"{part}.sc")
            return _answer(*_run("lint", str(Path(tmp) / f"{part}.sc"), "--limit", "50"))

    @server.tool()
    def predict_shape(part: str) -> CallToolResult:
        """Predicted bend and twist from the beam model, in seconds.

        The model cannot see misphased crossovers; the payload's `valid` says
        whether that check passed. part: as for lint_part.
        """
        return _answer(*_run("predict", part))

    @server.tool()
    def queue_status() -> CallToolResult:
        """What the oxDNA queue is doing: each job's state, stage and progress."""
        return _answer(*_run("sim", "status"))

    @server.tool()
    def experiment_list() -> CallToolResult:
        """Experiment folders under the root, by name."""
        names = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "pre").is_dir())
        return _answer(0, {"root": str(root), "experiments": names})

    @server.tool()
    def experiment_check(name: str) -> CallToolResult:
        """What an experiment folder is missing, and whether its record holds."""
        return with_folder(name, "experiment", "check")

    @server.tool()
    def experiment_report(name: str) -> CallToolResult:
        """Measure every raw scan, compare against the recorded prediction, write post/.

        Refuses, with error.kind, when the record cannot support a comparison:
        no measured tip radius, no prediction, a prediction newer than the data.
        """
        return with_folder(name, "experiment", "report")

    @server.tool()
    def experiment_compare_arms(name: str) -> CallToolResult:
        """E2's blinded two-arm comparison: fraction flat per arm, verdict both ways.

        Reads per-arm tip radii and the reference height from the record and
        refuses, with error.kind, when any is missing. Never asks which arm is
        which: the key stays with the person who holds it.
        """
        return with_folder(name, "experiment", "compare-arms")

    return server


def main(experiments_root: Path) -> None:
    """Serve over stdio until the client disconnects."""
    create_server(experiments_root).run("stdio")

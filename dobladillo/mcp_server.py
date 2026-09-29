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
experiment, writes a gate, writes the session log or the instrument record,
touches `during/raw/`, or commits. Ordering is a purchase, creating an
experiment is pre-registration, and the record is what happened at the bench:
each is the experimentalist's own act (`experiments/AGENTS.md`), done at the
CLI or in the local web UI (`dobladillo web`), never through here. An agent
may analyse, check and report. It may not pass a human gate, and the absence
of a tool is the strongest way to say so. `test_mcp_server.py` checks that list.

**Nothing may print.** On stdio the server's stdout IS the protocol stream,
so every command runs inside the CLI runner, which captures its output, and
nothing here writes to stdout directly.

**Where it can look.** Experiment folders are addressed by name, relative to
one root, and a name that resolves outside that root is refused. The server
runs on stdio only: it is a local process for a local agent, and the package
never calls out (`tests/test_licences.py`). Its one listener is the web UI,
bound to 127.0.0.1.

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

from dobladillo._invoke import run_json

#: Parts the tools accept by name.
PARTS: tuple[str, ...] = (
    "rectangle",
    "bundle",
    "hinge",
    "twist-corrected",
    "twist-uncorrected",
    "calibration-tile",
    "calibration-tile-biotin",
)

#: Commands an agent must never reach through this server, and why. The test
#: asserts no tool wraps any of them.
FORBIDDEN_COMMANDS: dict[str, str] = {
    "lab order": "an oligo order is a purchase, a human gate",
    "experiment new": "creating an experiment is pre-registration, the experimentalist's act",
    "experiment criterion": "the gate is the experimentalist's, written before the data",
    "experiment lock": "the lock commits the pre-registration; its time is evidence",
    "experiment log": "the session log is what happened at the bench, written by who was there",
    "experiment record": "an instrument reading an agent writes is a guess that looks measured",
    "experiment upload": "raw data enter the record only from the instrument, by its operator",
    "experiment commit": "a commit makes the record's times evidence; it is the experimentalist's",
    "web": "the web UI writes gates and records; it is for a person at the bench, not an agent",
}


def _run(*args: str) -> tuple[int, dict[str, Any]]:
    """Run a CLI command with --json in-process; return its exit code and payload."""
    return run_json(*args)


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

    def scan_file(name: str) -> Path | dict[str, Any]:
        candidate = (root / name).resolve()
        if root not in candidate.parents:
            return {"error": {"kind": "outside_root", "message": f"{name!r} is not under {root}"}}
        if not candidate.is_file():
            return {"error": {"kind": "missing_file", "message": f"no file {name!r}"}}
        return candidate

    def with_files(names: list[str], *command: str, after: tuple[str, ...] = ()) -> CallToolResult:
        paths = []
        for name in names:
            found = scan_file(name)
            if isinstance(found, dict):
                return _answer(2, found)
            paths.append(str(found))
        return _answer(*_run(*command, *paths, *after))

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

    @server.tool()
    def calibrate_reference() -> CallToolResult:
        """The calibration tile's reference geometry: mark positions in nm with their
        relative uncertainty. Nominal (design-derived), so not traceable."""
        return _answer(*_run("calibrate", "reference"))

    @server.tool()
    def calibrate_lateral(scans: list[str], reference: str = "calibration-tile") -> CallToolResult:
        """Scanner x/y scale and skew, with k=2 intervals, from scans of reference
        particles at random angles. scans: paths under the experiments root, same scan
        size and settings. reference: 'calibration-tile' or a reference JSON under the
        root. Refuses (error.kind calibration_refused) when the particles cannot separate
        scanner from sample."""
        if reference != "calibration-tile":
            found = scan_file(reference)
            if isinstance(found, dict):
                return _answer(2, found)
            reference = str(found)
        return with_files(scans, "calibrate", "lateral", after=("--reference", reference))

    @server.tool()
    def calibrate_tip(scan: str, size_px: int = 31) -> CallToolResult:
        """Blind tip reconstruction (an outer bound), its apex radius and the lateral
        resolution it allows. Says informative: false when the scan has no features
        sharp enough to constrain the tip."""
        return with_files([scan], "calibrate", "tip", after=("--size-px", str(size_px)))

    @server.tool()
    def calibrate_drift(frames: list[str], interval_s: float | None = None) -> CallToolResult:
        """Drift between frames of the same field: per-frame displacement and a velocity
        with its standard error. frames: paths under the root, in time order, with
        interval_s; or ONE high-speed movie (.asd, .h5-jpk), whose frame times come from
        the file unless interval_s is given (times_source says which)."""
        after = () if interval_s is None else ("--interval-s", str(interval_s))
        return with_files(frames, "calibrate", "drift", after=after)

    @server.tool()
    def calibrate_report(name: str) -> CallToolResult:
        """Every calibration a K folder's scans support: scale, tip and drift.

        Finds pattern-*/overlap-* (lateral), K4's S1-01 blocks (tip) and
        frame-* series (drift) in during/raw/, takes the conditions from
        during/instrument.json, and writes post/calibration.json with the
        scans' hashes, as experiment_report writes post/. Each analysis
        refuses, with error.kind, when a condition it depends on is not
        recorded. Never evaluates the gate."""
        return with_folder(name, "calibrate", "report")

    @server.tool()
    def experiment_pattern(name: str) -> CallToolResult:
        """E8: read the designed pattern off every well-formed particle, and which
        way round it lies. Refuses, with error.kind, when the record cannot
        support it."""
        return with_folder(name, "experiment", "pattern")

    @server.tool()
    def experiment_assembly(name: str) -> CallToolResult:
        """E9: monomer, dimer and larger fractions per sample, against the A-alone and
        B-alone controls. Refuses, with error.kind, when the record cannot support it."""
        return with_folder(name, "experiment", "assembly")

    @server.tool()
    def experiment_folding_screen(name: str) -> CallToolResult:
        """E11: folded yield against constant temperature and time, from the gel
        quantification, beside the predicted folding window."""
        return with_folder(name, "experiment", "folding-screen")

    @server.tool()
    def experiment_rods(name: str) -> CallToolResult:
        """E10: trace every rod, check its tip-corrected length, and tell a straight
        but flexible bundle from a systematically curved one. Refuses, with
        error.kind, when the record cannot support it."""
        return with_folder(name, "experiment", "rods")

    return server


def main(experiments_root: Path) -> None:
    """Serve over stdio until the client disconnects."""
    create_server(experiments_root).run("stdio")

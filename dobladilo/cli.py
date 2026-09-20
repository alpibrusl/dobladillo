"""Command line interface, readable by a person and parseable by an agent.

Every command takes `--json`. With it, stdout carries exactly one JSON object
and nothing else: no banners, no progress, no colour. Without it, the same data
is laid out for a human. The two are generated from one structure, so they
cannot drift apart and quietly disagree.

Three things make this usable by an agent rather than merely scriptable:

- `dobladilo describe --json` emits the whole command surface -- commands,
  parameters, types, defaults, output keys -- so capabilities can be discovered
  without scraping `--help`.
- Failures are JSON too, on stdout, with a stable `error` key and a non-zero
  exit code. An agent never has to tell a stack trace from a result.
- Warnings go to stderr, so a `--json` stdout stays machine-clean even when
  something is worth saying.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from dobladilo import __version__
from dobladilo import _scadnano as ad

app = typer.Typer(help="DNA origami brick toolchain.", no_args_is_help=True)
build_app = typer.Typer(help="Generate a part and write its files.", no_args_is_help=True)
app.add_typer(build_app, name="build")

JSON_OPTION = typer.Option(False, "--json", help="Emit one JSON object on stdout, nothing else.")
OUT_OPTION = typer.Option(None, "--out", help="Write .sc, cadnano v2 and oxview files here.")


@dataclass(frozen=True)
class Emitter:
    """Writes a result once, in whichever of the two shapes was asked for."""

    as_json: bool

    def result(self, payload: dict[str, Any], human: str) -> None:
        if self.as_json:
            typer.echo(json.dumps(payload, indent=2, sort_keys=False))
        else:
            typer.echo(human)

    def fail(self, message: str, *, kind: str = "error", code: int = 1) -> None:
        """Fail the same way in both modes: never a bare traceback."""
        if self.as_json:
            typer.echo(json.dumps({"error": {"kind": kind, "message": message}}, indent=2))
        else:
            typer.echo(f"error: {message}", err=True)
        raise typer.Exit(code)

    def note(self, message: str) -> None:
        """Say something without polluting a --json stdout."""
        typer.echo(message, err=True)


def _table(rows: list[tuple[str, str]], *, indent: str = "  ") -> str:
    if not rows:
        return ""
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{indent}{k.ljust(width)}  {v}" for k, v in rows)


@app.callback()
def main() -> None:
    """Group the commands under subcommands.

    Without a callback, typer collapses a single command into the root command,
    and `dobladilo version` fails on an unexpected argument.
    """


@app.command()
def version(as_json: bool = JSON_OPTION) -> None:
    """Print the version."""
    out = Emitter(as_json)
    out.result(
        {"version": __version__, "scadnano_pinned": ad.SCADNANO_PINNED},
        f"dobladilo {__version__}  (scadnano {ad.SCADNANO_PINNED})",
    )


@app.command()
def scaffolds(as_json: bool = JSON_OPTION) -> None:
    """List the scaffold strands available, asked of scadnano directly."""
    out = Emitter(as_json)
    available = ad.available_scaffolds()
    out.result(
        {"scaffolds": available},
        "Available scaffolds:\n"
        + _table([(name, f"{length:,} nt") for name, length in available.items()]),
    )


@app.command()
def geometry(as_json: bool = JSON_OPTION) -> None:
    """Show the geometry constants, and where this project disagrees.

    Worth a command of its own: dobladilo's literature rise per base pair and
    scadnano's differ by 2.4%, which lands straight in any predicted dimension.
    Surfacing it beats discovering it in a comparison report.
    """
    from dobladilo.constants import HELICAL_REPEAT_BP, RISE_PER_BP_NM

    out = Emitter(as_json)
    theirs = ad.GEOMETRY.rise_per_base_pair
    disagreement = abs(RISE_PER_BP_NM - theirs) / theirs

    payload = {
        "rise_per_bp_nm": {
            "dobladilo_literature": RISE_PER_BP_NM,
            "scadnano": theirs,
            "relative_difference": round(disagreement, 4),
            "rule": "predictions compared against scadnano or oxDNA output use scadnano's value",
        },
        "bases_per_turn": {
            "dobladilo": HELICAL_REPEAT_BP,
            "scadnano": ad.GEOMETRY.bases_per_turn,
        },
        "interhelix_spacing_nm": ad.interhelix_spacing_nm(),
    }
    human = (
        "Rise per base pair\n"
        + _table(
            [
                ("dobladilo (literature)", f"{RISE_PER_BP_NM} nm"),
                ("scadnano", f"{theirs} nm"),
                ("difference", f"{disagreement:.1%}"),
            ]
        )
        + "\n  Predictions compared against scadnano or oxDNA output use scadnano's value.\n"
        + f"\nBases per turn: {HELICAL_REPEAT_BP} (both)\n"
        + f"Inter-helix spacing: {ad.interhelix_spacing_nm()} nm"
    )
    out.result(payload, human)


def _build(
    *,
    out: Emitter,
    part: Any,
    directory: Path | None,
    name: str,
    verify: bool,
) -> None:
    payload = part.as_dict()

    if verify:
        payload["cadnano_v2_roundtrip"] = ad.roundtrips_through_cadnano_v2(part.design)

    if directory is not None:
        written = ad.write_all(part.design, directory=directory, name=name)
        payload["files"] = {k: str(v) for k, v in written.items()}

    scaffold = payload["scaffold"]
    rows = [
        ("lattice", payload["lattice"]),
        ("helices", str(payload["helices"])),
        ("length", f"{payload['length_bp']} bp"),
        (
            "scaffold",
            f"{scaffold['variant']}, {scaffold['routed_nt']:,} of "
            f"{scaffold['total_nt']:,} nt routed, {scaffold['unused_nt']:,} left as a loop",
        ),
        (
            "staples",
            f"{payload['staple_count']}, {payload['staple_length_nt']['min']}"
            f"-{payload['staple_length_nt']['max']} nt",
        ),
    ]
    if scaffold["deletions"]:
        rows.append(("deletions", f"{scaffold['deletions']} (twist correction)"))
    for key, value in payload["approx_dimensions_nm"].items():
        rows.append((f"{key} (nm)", str(value)))
    if "cadnano_v2_roundtrip" in payload:
        ok = payload["cadnano_v2_roundtrip"]
        rows.append(("cadnano v2 round trip", "ok" if ok else "FAILED"))
    if "files" in payload:
        rows.extend((f"wrote {k}", v) for k, v in payload["files"].items())

    out.result(payload, f"{payload['part']}\n" + _table(rows))


@build_app.command("rectangle")
def build_rectangle(
    helices: int = typer.Option(24, help="Number of helices. Must be even."),
    length: int = typer.Option(288, help="Bases per helix. Must be a multiple of 32."),
    scaffold: str = typer.Option("p7249", help="M13 variant."),
    twist_corrected: bool = typer.Option(True, help="Delete one base every 64 to cancel twist."),
    out_dir: Path | None = OUT_OPTION,
    name: str = typer.Option("rectangle", help="Base name for the written files."),
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """A Rothemund-style rectangle on the square lattice."""
    from dobladilo.parts.rectangle import rothemund_rectangle

    emitter = Emitter(as_json)
    try:
        part = rothemund_rectangle(
            helices=helices,
            length=length,
            scaffold_variant=scaffold,
            twist_corrected=twist_corrected,
        )
    except ValueError as e:
        emitter.fail(str(e), kind="invalid_parameters")
        return
    _build(out=emitter, part=part, directory=out_dir, name=name, verify=verify)


@build_app.command("bundle")
def build_bundle(
    length: int = typer.Option(1176, help="Bases per helix. Must be a multiple of 42."),
    scaffold: str = typer.Option("p7249", help="M13 variant."),
    out_dir: Path | None = OUT_OPTION,
    name: str = typer.Option("bundle", help="Base name for the written files."),
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """A six-helix bundle on the honeycomb lattice."""
    from dobladilo.parts.bundle import six_helix_bundle

    emitter = Emitter(as_json)
    try:
        part = six_helix_bundle(length=length, scaffold_variant=scaffold)
    except ValueError as e:
        emitter.fail(str(e), kind="invalid_parameters")
        return
    _build(out=emitter, part=part, directory=out_dir, name=name, verify=verify)


@app.command()
def describe(as_json: bool = JSON_OPTION) -> None:
    """Emit the command surface, for an agent to read instead of `--help`.

    Generated by walking the typer app, so a command added without touching
    this function still appears. The point is that a caller can discover what
    exists, what it takes and what it returns in one parseable object.
    """
    out = Emitter(as_json)
    cli = typer.main.get_command(app)
    commands: list[dict[str, Any]] = []

    def is_group(cmd: Any) -> bool:
        # Duck-typed on purpose. typer 0.27 vendors click as `typer._click`, so
        # `import click` fails and `isinstance(cmd, click.Group)` cannot be
        # written without reaching into a private module. Having subcommands is
        # what actually matters here.
        return hasattr(cmd, "commands")

    def is_option(param: Any) -> bool:
        return getattr(param, "param_type_name", None) == "option"

    def walk(group: Any, prefix: list[str]) -> None:
        for cname, cmd in sorted(group.commands.items()):
            path = [*prefix, cname]
            if is_group(cmd):
                walk(cmd, path)
                continue
            params = [
                {
                    "name": p.name,
                    "flags": list(p.opts),
                    "type": getattr(p.type, "name", str(p.type)),
                    "default": str(p.default) if isinstance(p.default, Path) else p.default,
                    "required": bool(p.required),
                    "help": getattr(p, "help", None),
                }
                for p in cmd.params
                if is_option(p)
            ]
            help_text = (cmd.help or "").strip()
            commands.append(
                {
                    "command": " ".join(path),
                    "summary": help_text.splitlines()[0] if help_text else "",
                    "options": params,
                }
            )

    walk(cli, [])
    payload = {
        "tool": "dobladilo",
        "version": __version__,
        "conventions": {
            "json_flag": "--json makes stdout exactly one JSON object",
            "errors": "failures print {'error': {'kind', 'message'}} and exit non-zero",
            "stderr": "warnings and notes go to stderr, never into a --json stdout",
        },
        "commands": commands,
    }
    human = "Commands:\n" + _table([(c["command"], c["summary"]) for c in commands])
    out.result(payload, human)


if __name__ == "__main__":
    app()

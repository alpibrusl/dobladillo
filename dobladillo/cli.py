"""Command line interface, readable by a person and parseable by an agent.

Every command takes `--json`. With it, stdout carries exactly one JSON object
and nothing else: no banners, no progress, no colour. Without it, the same data
is laid out for a human. The two are generated from one structure, so they
cannot drift apart and quietly disagree.

Three things make this usable by an agent rather than merely scriptable:

- `dobladillo describe --json` emits the whole command surface -- commands,
  parameters, types, defaults, output keys -- so capabilities can be discovered
  without scraping `--help`.
- Failures are JSON too, on stdout, with a stable `error` key and a non-zero
  exit code. An agent never has to tell a stack trace from a result.
- Warnings go to stderr, so a `--json` stdout stays machine-clean even when
  something is worth saying.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from dobladillo import __version__
from dobladillo import _scadnano as ad
from dobladillo.parts import bundle as _bundle
from dobladillo.parts import hinge as _hinge
from dobladillo.parts import rectangle as _rectangle

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
    and `dobladillo version` fails on an unexpected argument.
    """


@app.command()
def version(as_json: bool = JSON_OPTION) -> None:
    """Print the version."""
    out = Emitter(as_json)
    out.result(
        {"version": __version__, "scadnano_pinned": ad.SCADNANO_PINNED},
        f"dobladillo {__version__}  (scadnano {ad.SCADNANO_PINNED})",
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

    Worth a command of its own: dobladillo's literature rise per base pair and
    scadnano's differ by 2.4%, which lands straight in any predicted dimension.
    Surfacing it beats discovering it in a comparison report.
    """
    from dobladillo.constants import HELICAL_REPEAT_BP, RISE_PER_BP_NM

    out = Emitter(as_json)
    theirs = ad.GEOMETRY.rise_per_base_pair
    disagreement = abs(RISE_PER_BP_NM - theirs) / theirs

    payload = {
        "rise_per_bp_nm": {
            "dobladillo_literature": RISE_PER_BP_NM,
            "scadnano": theirs,
            "relative_difference": round(disagreement, 4),
            "rule": "predictions compared against scadnano or oxDNA output use scadnano's value",
        },
        "bases_per_turn": {
            "dobladillo": HELICAL_REPEAT_BP,
            "scadnano": ad.GEOMETRY.bases_per_turn,
        },
        "interhelix_spacing_nm": ad.interhelix_spacing_nm(),
    }
    human = (
        "Rise per base pair\n"
        + _table(
            [
                ("dobladillo (literature)", f"{RISE_PER_BP_NM} nm"),
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
    # A hinge names its helices and length per arm, because it has two of each.
    helices = payload.get("helices", payload.get("arm_helices"))
    length_bp = payload.get("length_bp", payload.get("arm_length_bp"))
    dimensions = payload.get("approx_dimensions_nm") or payload["approx_arm_dimensions_nm"]
    rows = [
        ("lattice", payload["lattice"]),
        ("helices", str(helices)),
        ("length", f"{length_bp} bp" + (" per arm" if "arm_length_bp" in payload else "")),
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
    if "joint_nt" in payload:
        latch = payload["latch"]
        rows.append(("joint", f"{payload['joint_nt']} unpaired nt per helix"))
        rows.append(
            (
                "latch",
                f"{latch['sequence']} ({latch['length_bp']} bp, "
                f"{latch['gc_fraction']:.0%} GC) on helix {latch['helix']}",
            )
        )
        rows.append(("predicted field", f"{payload['predicted_field_kt']} kT, sequence only"))
        rows.append(("conformational offset", payload["conformational_offset"]))
    for key, value in dimensions.items():
        rows.append((f"{key} (nm)", str(value)))
    if "cadnano_v2_roundtrip" in payload:
        ok = payload["cadnano_v2_roundtrip"]
        rows.append(("cadnano v2 round trip", "ok" if ok else "FAILED"))
    if "files" in payload:
        rows.extend((f"wrote {k}", v) for k, v in payload["files"].items())

    out.result(payload, f"{payload['part']}\n" + _table(rows))


@build_app.command("rectangle")
def build_rectangle(
    helices: int = typer.Option(
        _rectangle.DEFAULT_HELICES, help="Number of helices. Must be even."
    ),
    length: int = typer.Option(
        _rectangle.DEFAULT_LENGTH, help="Bases per helix. Must be a multiple of 64."
    ),
    scaffold: str = typer.Option("p7249", help="M13 variant."),
    twist_corrected: bool = typer.Option(True, help="Delete one base every 64 to cancel twist."),
    out_dir: Path | None = OUT_OPTION,
    name: str = typer.Option("rectangle", help="Base name for the written files."),
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """A Rothemund-style rectangle on the square lattice."""
    from dobladillo.parts.rectangle import rothemund_rectangle

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


@build_app.command("hinge")
def build_hinge(
    arm_helices: int = typer.Option(
        _hinge.DEFAULT_ARM_HELICES, help="Helices per arm. Must be even."
    ),
    arm_length: int = typer.Option(
        _hinge.DEFAULT_ARM_LENGTH, help="Bases per arm. Must be a multiple of 64."
    ),
    joint: int = typer.Option(
        _hinge.DEFAULT_JOINT_NT, help="Unpaired scaffold bases per helix at the joint."
    ),
    latch: str = typer.Option(_hinge.DEFAULT_LATCH, help="Latch sequence, 5' to 3'."),
    latch_helix: int = typer.Option(_hinge.DEFAULT_LATCH_HELIX, help="Helix the latch hangs from."),
    scaffold: str = typer.Option("p7249", help="M13 variant."),
    twist_corrected: bool = typer.Option(True, help="Delete one base every 64 to cancel twist."),
    out_dir: Path | None = OUT_OPTION,
    name: str = typer.Option("hinge", help="Base name for the written files."),
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """A bistable hinge: two arms, a single-stranded joint, and a latch."""
    from dobladillo.parts.hinge import bistable_hinge

    emitter = Emitter(as_json)
    try:
        part = bistable_hinge(
            arm_helices=arm_helices,
            arm_length=arm_length,
            joint_nt=joint,
            latch_sequence=latch,
            latch_helix=latch_helix,
            scaffold_variant=scaffold,
            twist_corrected=twist_corrected,
        )
    except ValueError as e:
        emitter.fail(str(e), kind="invalid_parameters")
        return
    _build(out=emitter, part=part, directory=out_dir, name=name, verify=verify)


@build_app.command("bundle")
def build_bundle(
    length: int = typer.Option(
        _bundle.DEFAULT_LENGTH, help="Bases per helix. Must be a multiple of 42."
    ),
    scaffold: str = typer.Option("p7249", help="M13 variant."),
    out_dir: Path | None = OUT_OPTION,
    name: str = typer.Option("bundle", help="Base name for the written files."),
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """A six-helix bundle on the honeycomb lattice."""
    from dobladillo.parts.bundle import six_helix_bundle

    emitter = Emitter(as_json)
    try:
        part = six_helix_bundle(length=length, scaffold_variant=scaffold)
    except ValueError as e:
        emitter.fail(str(e), kind="invalid_parameters")
        return
    _build(out=emitter, part=part, directory=out_dir, name=name, verify=verify)


lab_app = typer.Typer(help="What the bench needs: plates, pooling, protocol.", no_args_is_help=True)
app.add_typer(lab_app, name="lab")

PART_ARGUMENT = typer.Argument(..., help="Which part: rectangle or bundle.")
PLATE_OPTION = typer.Option(96, "--plate", help="Well plate format: 96 or 384.")

LIMIT_OPTION = typer.Option(20, "--limit", help="Most findings to list. 0 for all.")
ONLY_OPTION = typer.Option(None, "--rule", help="Run only this rule. Repeatable.")


@app.command()
def rules(as_json: bool = JSON_OPTION) -> None:
    """List the design rules, and what is knowingly not checked."""
    from dobladillo.routing.rules import RULES, UNIMPLEMENTED

    out = Emitter(as_json)
    out.result(
        {
            "rules": [{"name": r.name, "summary": r.summary} for r in RULES],
            "not_checked": [{"rule": n, "why": w} for n, w in UNIMPLEMENTED],
        },
        "Rules:\n"
        + _table([(r.name, r.summary) for r in RULES])
        + "\n\nNot checked:\n"
        + _table([(n, w) for n, w in UNIMPLEMENTED]),
    )


@app.command()
def lint(
    design_file: Path = typer.Argument(..., help="A .sc design file."),
    only: list[str] | None = ONLY_OPTION,
    limit: int = LIMIT_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Check a design against the rules. Exits non-zero on a hard violation.

    Warnings never change the exit code: they are preferences that published
    designs break routinely, and a lint that fails on them would just be
    switched off.
    """
    from dobladillo.routing.rules import lint as run_lint

    out = Emitter(as_json)
    if not design_file.is_file():
        out.fail(f"no such file: {design_file}", kind="missing_file", code=2)
        return
    try:
        design = ad.read_design(design_file)
    except Exception as e:  # scadnano raises several unrelated types
        out.fail(f"could not read {design_file}: {e}", kind="unreadable_design", code=2)
        return

    try:
        report = run_lint(design, only=only or None)
    except ValueError as e:
        out.fail(str(e), kind="unknown_rule")
        return

    payload = report.as_dict(limit=None if limit == 0 else limit)
    payload["design"] = str(design_file)

    counts = payload["counts"]
    head = (
        f"{design_file}: {counts['violations']} violations, {counts['warnings']} warnings"
        if report.violations
        else f"{design_file}: clean"
    )
    lines = [head]
    if payload["by_rule"]:
        lines.append(_table([(k, str(v)) for k, v in payload["by_rule"].items()]))
    for finding in payload["findings"]:
        where = f"helix {finding['helix']} offset {finding['offset']}"
        lines.append(
            f"  {finding['severity']:9s} {finding['rule']:20s} {finding['message']} [{where}]"
        )
    if payload["truncated"]:
        lines.append("  ... more not shown; raise --limit (0 for all)")
    lines.append("  not checked: " + ", ".join(e["rule"] for e in payload["not_checked"]))
    out.result(payload, "\n".join(lines))

    if not report.ok:
        raise typer.Exit(1)


def _make_part(which: str, out: Emitter) -> Any:
    if which == "rectangle":
        from dobladillo.parts.rectangle import rothemund_rectangle

        return rothemund_rectangle()
    if which == "bundle":
        from dobladillo.parts.bundle import six_helix_bundle

        return six_helix_bundle()
    if which in ("twist-corrected", "twist-uncorrected"):
        from dobladillo.parts.twist_pair import twist_pair

        pair = twist_pair()
        return pair.corrected if which == "twist-corrected" else pair.uncorrected
    out.fail(
        f"unknown part {which!r}; use rectangle, bundle, twist-corrected or twist-uncorrected",
        kind="unknown_part",
    )
    return None


@lab_app.command("order")
def lab_order(
    part: str = PART_ARGUMENT,
    out_dir: Path | None = OUT_OPTION,
    plate: int = PLATE_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Plates, pooling map and cost for ordering a part's staples.

    Validates what it writes rather than trusting that no exception means a
    file IDT would accept.
    """
    from dobladillo.lab import plates as lab

    emitter = Emitter(as_json)
    if plate not in (96, 384):
        emitter.fail(f"plate must be 96 or 384, got {plate}", kind="invalid_parameters")
        return
    built = _make_part(part, emitter)
    layout = lab.name_and_assign_wells(built.design, plate_type=plate)

    problems = lab.validate_bulk_csv(lab.bulk_csv_rows(built.design))
    payload: dict[str, Any] = {
        "part": part,
        **layout.as_dict(),
        "pooling": layout.pooling_map(),
        "pipetting": lab.pipetting_sheet(layout),
        "problems": [p.as_dict() for p in problems],
    }

    if out_dir is not None:
        written = lab.write_order_files(
            built.design, directory=out_dir, name=part, plate_type=plate
        )
        problems += lab.validate_plate_workbook(written["idt_plate_xlsx"], plate_type=plate)
        payload["problems"] = [p.as_dict() for p in problems]
        payload["files"] = {k: str(v) for k, v in written.items()}

    payload["valid"] = not problems

    cost = layout.cost
    rows = [
        ("plates", f"{len(layout.plates)} x {plate}-well: {', '.join(layout.plates)}"),
        ("staples", str(len(layout.wells))),
        ("total bases", f"{cost.total_nt:,}"),
        ("estimated cost", f"{cost.total:,.2f} at {cost.price_per_base}/base"),
        ("order files valid", "yes" if not problems else f"NO, {len(problems)} problems"),
    ]
    rows.extend((f"wrote {k}", v) for k, v in payload.get("files", {}).items())
    body = f"{part}: staple order\n" + _table(rows)
    body += "\n\n  Cost assumptions:\n" + _table([("-", a) for a in cost.assumptions])
    for problem in problems[:10]:
        body += f"\n  PROBLEM {problem.where}: {problem.message}"
    emitter.result(payload, body)

    if problems:
        raise typer.Exit(1)


@lab_app.command("protocol")
def lab_protocol(
    part: str = PART_ARGUMENT,
    volume_ul: float = typer.Option(50.0, help="Volume of each folding reaction."),
    as_json: bool = JSON_OPTION,
) -> None:
    """The folding protocol sheet, with the magnesium screen laid out."""
    from dobladillo.lab.protocol import folding_protocol

    emitter = Emitter(as_json)
    built = _make_part(part, emitter)
    info = built.as_dict()
    sheet = folding_protocol(
        part_name=part,
        dimensionality="2D" if info["lattice"] == "square" else "3D",
        scaffold_variant=info["scaffold"]["variant"],
        reaction_volume_ul=volume_ul,
    )

    anneal = sheet["anneal"]
    rows = [
        (
            "buffer",
            f"{sheet['buffer']['tris_mm']} mM Tris, "
            f"{sheet['buffer']['edta_mm']} mM EDTA, pH {sheet['buffer']['ph']}",
        ),
        ("Mg2+ screen", ", ".join(f"{m:g}" for m in sheet["magnesium_screen_mm"]) + " mM"),
        ("reactions", f"{len(sheet['reactions'])} x {volume_ul:g} ul"),
        ("hold", f"{anneal['hold']['temperature_c']} C for {anneal['hold']['minutes']:g} min"),
        (
            "ramp",
            f"{anneal['ramp']['from_c']} to {anneal['ramp']['to_c']} C "
            f"at {anneal['ramp']['rate']:g} {anneal['ramp']['rate_unit']}",
        ),
        ("total", f"{anneal['total_hours']} h"),
        ("purification", " / ".join(sheet["purification"])),
    ]
    body = f"{part}: folding protocol\n" + _table(rows)
    body += "\n\n  Record for each reaction:\n" + _table(
        [("-", r) for r in sheet["record_for_each_reaction"]]
    )
    body += f"\n\n  {sheet['note']}"
    emitter.result(sheet, body)


sim_app = typer.Typer(help="Simulation job bundles.", no_args_is_help=True)
app.add_typer(sim_app, name="sim")


@sim_app.command("bundle")
def sim_bundle(
    part: str = PART_ARGUMENT,
    out_dir: Path = typer.Option(..., "--out", help="Directory to write the bundle into."),
    backend: str = typer.Option("CUDA", help="oxDNA backend for the real run: CPU or CUDA."),
    test_mode: bool = typer.Option(
        False, "--test", help="Short stages, CPU, to prove the bundle runs end to end."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Write a self-contained oxDNA job bundle. Runs nothing.

    The bundle is generated and checked for structure; executing it is the
    human's job, on a machine with the backend it asks for. The metadata says
    so, so nothing downstream can mistake a bundle for a result.
    """
    from dobladillo.sim.jobs import write_job_bundle

    emitter = Emitter(as_json)
    built = _make_part(part, emitter)
    try:
        job = write_job_bundle(
            built.design,
            directory=out_dir,
            name=part,
            part=part,
            backend=backend,
            test_mode=test_mode,
        )
    except ValueError as e:
        emitter.fail(str(e), kind="invalid_parameters")
        return

    meta = job.metadata
    rows = [
        ("directory", str(job.directory)),
        ("nucleotides", f"{job.nucleotides:,}"),
        ("trapped pairs", f"{job.trapped_pairs:,}"),
        ("stages", " -> ".join(meta["protocol"]["stages"])),
        ("backend", "CPU (test mode)" if test_mode else backend),
        ("salt proxy", f"{meta['model']['salt_concentration_m']} M Na+"),
        ("status", meta["status"]),
    ]
    body = f"{part}: oxDNA job bundle\n" + _table(rows)
    body += f"\n\n  {meta['owed_by_human']}"
    body += f"\n\n  Protocol note: {meta['protocol']['deviation_from_design_doc']}"
    emitter.result(job.as_dict(), body)


@sim_app.command("check")
def sim_check(
    run_dir: Path = typer.Argument(..., help="A finished run directory."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Is this run something whose numbers mean anything? Exits non-zero if not."""
    from dobladillo.analysis.runs import check_run

    out = Emitter(as_json)
    if not run_dir.is_dir():
        out.fail(f"no such directory: {run_dir}", kind="missing_directory", code=2)
        return
    check = check_run(run_dir)
    rows = [("directory", str(run_dir)), ("usable as a result", "yes" if check.ok else "NO")]
    for key, value in check.metadata.get("steps", {}).items():
        rows.append((key, f"{value:,}"))
    body = "run check\n" + _table(rows)
    for problem in check.problems:
        body += f"\n  PROBLEM  {problem}"
    out.result(check.as_dict(), body)
    if not check.ok:
        raise typer.Exit(1)


@app.command("analyse")
def analyse_run(
    run_dir: Path = typer.Argument(..., help="A finished run directory."),
    skip: int = typer.Option(0, help="Frames to discard as equilibration."),
    out_dir: Path | None = OUT_OPTION,
    allow_test_mode: bool = typer.Option(
        False, "--allow-test-mode", help="Analyse a smoke test anyway. It is not a result."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Turn a finished run into observables with experimental counterparts.

    Refuses a run that has not passed its check, because a trajectory from an
    unfinished or test-mode bundle produces numbers that look exactly like
    real ones.
    """
    import json as _json

    from dobladillo.analysis.observables import (
        FRAMES_FOR_A_TRUSTWORTHY_RMSF,
        analyse,
        oxview_overlay,
    )
    from dobladillo.analysis.runs import NotAResult, load_run

    emitter = Emitter(as_json)
    if not run_dir.is_dir():
        emitter.fail(f"no such directory: {run_dir}", kind="missing_directory", code=2)
        return
    try:
        frames, check = load_run(run_dir, skip=skip, allow_test_mode=allow_test_mode)
    except NotAResult as e:
        emitter.fail(str(e), kind="not_a_result")
        return
    except ValueError as e:
        emitter.fail(str(e), kind="unusable_trajectory")
        return

    report = analyse(frames)
    payload = report.as_dict()
    payload["conditions"] = check.metadata.get("model", {})
    payload["is_smoke_test"] = bool(check.metadata.get("test_mode"))

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "observables.json").write_text(_json.dumps(payload, indent=2))
        (out_dir / "rmsf_overlay.json").write_text(_json.dumps(oxview_overlay(report.rmsf_nm)))
        payload["files"] = {
            "observables": str(out_dir / "observables.json"),
            "rmsf_overlay": str(out_dir / "rmsf_overlay.json"),
        }

    dims = payload["dimensions_nm"]
    rows = [
        ("frames", f"{report.frames} (steps {report.first_step:,}-{report.last_step:,})"),
        ("longest", f"{dims['longest']['mean']:.1f} +- {dims['longest']['sd']:.2f} nm"),
        ("middle", f"{dims['middle']['mean']:.1f} +- {dims['middle']['sd']:.2f} nm"),
        ("shortest", f"{dims['shortest']['mean']:.1f} +- {dims['shortest']['sd']:.2f} nm"),
        ("out of plane", f"{payload['planarity_nm']['mean']:.2f} nm RMS"),
        ("axis bend", f"{payload['bend_nm']['mean']:.2f} nm"),
        ("RMSF", f"mean {payload['rmsf_nm']['mean']:.2f}, max {payload['rmsf_nm']['max']:.2f} nm"),
        ("salt", f"{payload['conditions'].get('salt_concentration_m')} M Na+ (Mg2+ proxy)"),
    ]
    rows.extend((f"wrote {k}", v) for k, v in payload.get("files", {}).items())
    # The JSON carries `undersampled`; a person reading the table would not see
    # it, and the table is the half that gets pasted into a message.
    if payload["undersampled"]:
        error = payload["rmsf_nm"]["relative_standard_error"]
        rows.append(
            (
                "NOT ENOUGH FRAMES",
                f"{report.frames} frames carry a {error:.0%} standard error on every "
                f"spread above; {FRAMES_FOR_A_TRUSTWORTHY_RMSF} is the floor",
            )
        )
    body = "observables\n" + _table(rows)
    if payload["is_smoke_test"]:
        body += "\n\n  THESE ARE NOT RESULTS: the run is a smoke test, analysed under protest."
    emitter.result(payload, body)


@build_app.command("pair")
def build_pair(
    out_dir: Path | None = OUT_OPTION,
    verify: bool = typer.Option(False, help="Also check the cadnano v2 round trip."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Both arms of the twist pair, written side by side.

    One command rather than two, because the arms are only evidence together:
    building them separately invites building them at different times, from
    different parameters, which is exactly what the experiment must not do.
    """
    from dobladillo.parts.twist_pair import twist_pair

    emitter = Emitter(as_json)
    pair = twist_pair()
    payload: dict[str, Any] = pair.as_dict()

    for name, arm in (("corrected", pair.corrected), ("uncorrected", pair.uncorrected)):
        if verify:
            payload["arms"][name]["cadnano_v2_roundtrip"] = ad.roundtrips_through_cadnano_v2(
                arm.design
            )
        if out_dir is not None:
            written = ad.write_all(arm.design, directory=out_dir / name, name=name)
            payload["arms"][name]["files"] = {k: str(v) for k, v in written.items()}

    geometry = payload["geometry"]
    rows = [
        ("geometry", f"{geometry['helices']} helices x {geometry['length_bp']} bp"),
        ("differs only in", payload["differs_only_in"]),
        (
            "predicted twist",
            f"{payload['predicted_twist_of_uncorrected_deg']:.0f} deg, uncorrected arm",
        ),
    ]
    for name in ("corrected", "uncorrected"):
        arm_info = payload["arms"][name]
        rows.append((name, f"{arm_info['staples']} staples, {arm_info['deletions']} deletions"))
        for key, value in arm_info.get("files", {}).items():
            rows.append((f"  {name} {key}", value))
    emitter.result(payload, "twist pair\n" + _table(rows))


QUEUE_ROOT_OPTION = typer.Option(
    Path("oxqueue"), "--root", help="Queue directory. One file per job lives under it."
)
OXDNA_OPTION = typer.Option(
    None, "--oxdna", envvar="OXDNA", help="Path to the oxDNA binary. Defaults to $OXDNA or PATH."
)


@sim_app.command("enqueue")
def sim_enqueue(
    bundles: list[Path] = typer.Argument(..., help="Bundle directories to queue."),
    root: Path = QUEUE_ROOT_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """Add bundles to the queue. Starts nothing; `sim run` does that."""
    from dobladillo.sim.queue import enqueue

    emitter = Emitter(as_json)
    added = []
    for bundle in bundles:
        try:
            added.append(enqueue(root, bundle))
        except ValueError as e:
            emitter.fail(str(e), kind="not_a_bundle")
            return
    payload = {"root": str(root), "queued": [{"id": j.id, "bundle": j.bundle} for j in added]}
    rows = [(j.id, j.bundle) for j in added]
    emitter.result(payload, f"queued {len(added)}\n" + _table(rows))


@sim_app.command("run")
def sim_run(
    root: Path = QUEUE_ROOT_OPTION,
    workers: int | None = typer.Option(
        None, help="Jobs to run at once. Defaults to cores minus four."
    ),
    oxdna: str | None = OXDNA_OPTION,
    once: bool = typer.Option(
        False, "--once", help="Drain what is queued now and stop, rather than waiting for more."
    ),
    as_json: bool = JSON_OPTION,
) -> None:
    """Run queued bundles, several at a time. Blocks; launch it with nohup.

    oxDNA's CPU backend is single-threaded, so the useful number of workers is
    close to the core count, and running one job at a time leaves most of the
    machine idle for hours.
    """
    from dobladillo.sim.queue import run

    emitter = Emitter(as_json)
    binary = oxdna or "oxDNA"
    if shutil.which(binary) is None and not Path(binary).exists():
        emitter.fail(f"oxDNA not found at {binary!r}; set --oxdna or $OXDNA", kind="no_oxdna")
        return
    outcome = run(root, oxdna=binary, workers=workers, once=once)
    emitter.result(
        outcome,
        "queue drained\n" + _table([(k, str(v)) for k, v in outcome.items()]),
    )


@sim_app.command("status")
def sim_status(
    root: Path = QUEUE_ROOT_OPTION,
    as_json: bool = JSON_OPTION,
) -> None:
    """What the queue is doing."""
    from dobladillo.sim.queue import status

    payload = status(root)
    rows = []
    for job in payload["jobs"]:
        stage = job["stage"] or "-"
        detail = job["state"]
        if job["state"] == "running":
            done, total = (job["progress"].get(stage) or {"steps": 0, "of": 0}).values()
            share = f"{100 * done / total:.0f}%" if total else "?"
            detail = f"running {stage} {share}"
        elif job["state"] == "failed":
            detail = f"FAILED {job['error']}"
        rows.append((job["label"], detail))
    counts = ", ".join(f"{v} {k}" for k, v in sorted(payload["counts"].items())) or "empty"
    Emitter(as_json).result(payload, f"queue: {counts}\n" + _table(rows))


@sim_app.command("sweep")
def sim_sweep(
    joint: str = typer.Option(
        "4,8,16,32", help="Comma-separated joint lengths, in unpaired nt per helix."
    ),
    out_dir: Path = typer.Option(..., "--out", help="Directory to write the bundles into."),
    root: Path = QUEUE_ROOT_OPTION,
    steps: int = typer.Option(
        1_000_000, help="Production steps per bundle. A million is about 6.5 h on one core."
    ),
    relax: int = typer.Option(
        100_000,
        help="Steps per relaxation stage. 100k is what the completed six-helix run used.",
    ),
    enqueue_them: bool = typer.Option(True, "--enqueue/--no-enqueue", help="Also queue them."),
    as_json: bool = JSON_OPTION,
) -> None:
    """Build one hinge bundle per joint length, and queue them.

    The sweep the hinge needs first: whether the latch can physically reach
    across the joint is geometry the constructor cannot settle, and a joint
    too long costs conformational entropy while one too short holds the
    mechanism open. Both ends show up here and nowhere else.

    The relaxation default is 100k rather than the library's million, because
    100k is what the six-helix run that actually completed on this machine
    used. At a million, relaxation alone would be thirteen hours a job and the
    sweep would not finish overnight.
    """
    from dobladillo.parts.hinge import bistable_hinge
    from dobladillo.sim.jobs import write_job_bundle
    from dobladillo.sim.queue import enqueue

    emitter = Emitter(as_json)
    try:
        lengths = [int(v) for v in joint.split(",") if v.strip()]
    except ValueError:
        emitter.fail(f"could not read joint lengths from {joint!r}", kind="invalid_parameters")
        return
    if not lengths:
        emitter.fail("no joint lengths given", kind="invalid_parameters")
        return

    built = []
    for length in lengths:
        name = f"hinge-joint{length}"
        try:
            part = bistable_hinge(joint_nt=length)
            job = write_job_bundle(
                part.design,
                directory=out_dir / name,
                name=name,
                part="hinge",
                backend="CPU",
                steps_override={"steps_production": steps, "steps_relax": relax},
            )
        except ValueError as e:
            emitter.fail(str(e), kind="invalid_parameters")
            return
        entry: dict[str, Any] = {
            "joint_nt": length,
            "bundle": str(job.directory),
            "nucleotides": job.nucleotides,
        }
        if enqueue_them:
            entry["id"] = enqueue(root, job.directory, label=name, meta={"joint_nt": length}).id
        built.append(entry)
    rows = [(f"{b['joint_nt']} nt", str(b["bundle"])) for b in built]
    emitter.result(
        {"bundles": built, "root": str(root), "production_steps": steps},
        f"hinge joint sweep, {len(built)} bundles\n" + _table(rows),
    )


@app.command("bracket")
def bracket_command(as_json: bool = JSON_OPTION) -> None:
    """The latch ladder that guarantees Stage 0 lands in its measurement window."""
    from dobladillo.hamiltonian.bracket import ladder

    rungs = ladder()
    low, high = rungs.offset_range_kt
    payload = {
        "window_kt": round(rungs.window_kt, 3),
        "rungs": [
            {"sequence": r.sequence, "length_bp": r.length_bp, "field_kt": round(r.field_kt, 2)}
            for r in rungs.rungs
        ],
        "largest_gap_kt": round(rungs.largest_gap_kt, 3),
        "covers_its_range": rungs.covers_its_range,
        "measurable_conformational_offset_kt": [round(low, 1), round(high, 1)],
    }
    rows = [(r.sequence, f"{r.length_bp} bp, h = {r.field_kt:.2f} kT") for r in rungs.rungs]
    Emitter(as_json).result(payload, rungs.summary() + "\n" + _table(rows))


@app.command("twist-pair")
def twist_pair_command(as_json: bool = JSON_OPTION) -> None:
    """The matched pair that tests whether the twist correction does anything."""
    from dobladillo.lab.plates import name_and_assign_wells
    from dobladillo.parts.twist_pair import twist_pair

    out = Emitter(as_json)
    pair = twist_pair()
    payload = pair.as_dict()
    cost: dict[str, float] = {
        arm: name_and_assign_wells(getattr(pair, arm).design).cost.total
        for arm in ("corrected", "uncorrected")
    }
    cost["total"] = sum(cost.values())
    payload["cost"] = cost

    geometry = payload["geometry"]
    rows = [
        ("geometry", f"{geometry['helices']} helices x {geometry['length_bp']} bp"),
        (
            "size",
            f"{geometry['approx_nm']['width']:.0f} x {geometry['approx_nm']['height']:.0f} nm",
        ),
        ("differs only in", payload["differs_only_in"]),
        (
            "predicted twist",
            f"{payload['predicted_twist_of_uncorrected_deg']:.0f} deg, uncorrected",
        ),
        ("corrected", f"{payload['arms']['corrected']['deletions']} deletions, lies flat"),
        ("uncorrected", "no deletions, cannot lie flat"),
        ("cost", f"{payload['cost']['total']:.0f} for both arms"),
    ]
    body = "twist pair\n" + _table(rows) + f"\n\n  Readout: {payload['readout']}"
    out.result(payload, body)


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
        "tool": "dobladillo",
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


SKILL_DISCIPLINE = """\
## Working rules

These matter more than the command list. The toolchain is built so that a
mistake here is refused rather than absorbed, but an agent that fights the
refusals can still produce nonsense.

1. **Never present a generated artefact as a result.** A job bundle is not a
   simulation; an order file is not a folded sample. Every bundle's metadata
   says `status: not run`, and `analyse` refuses a run that has not passed
   `sim check`. Do not pass `--allow-test-mode` to get a number.
2. **Every command takes `--json`.** Use it. stdout is then exactly one JSON
   object, failures included, with a stable `error.kind` and a non-zero exit.
3. **Conditions travel with numbers.** oxDNA2 has no explicit magnesium, so a
   prediction made at one proxy salt is not comparable to one made at another,
   nor directly to a measurement in a magnesium buffer. Never join two
   observables without checking their conditions.
4. **Respect the human gates.** Simulation runs on a machine with CUDA;
   folding and imaging happen in a lab. If `data/` lacks what a task needs,
   produce the bundle or request sheet and stop with a clear note of what is
   owed.
5. **Physical constants live in `dobladillo/constants.py`**, each with its
   source. Do not inline a number; if one is wrong, change it there.
6. **Run `dobladillo lint` before anything expensive.** Hard violations block
   ordering and simulating for a reason: both cost money or days.
"""


def _skill_markdown() -> str:
    """The skill file, generated from the live command surface.

    Generated rather than written so it cannot drift from what the tool
    actually accepts -- the same reason `describe` walks the app.
    """
    cli = typer.main.get_command(app)
    lines: list[str] = []

    def walk(group: Any, prefix: list[str]) -> None:
        for name, cmd in sorted(group.commands.items()):
            path = [*prefix, name]
            if hasattr(cmd, "commands"):
                walk(cmd, path)
                continue
            help_text = (cmd.help or "").strip()
            summary = help_text.splitlines()[0] if help_text else ""
            lines.append(f"- `dobladillo {' '.join(path)}` — {summary}")

    walk(cli, [])
    commands = "\n".join(lines)
    return f"""---
name: dobladillo
description: "Design, simulate and order DNA origami bricks. Commands: build, \
lint, lab, sim, analyse…"
---

# dobladillo

> Auto-generated skill file for dobladillo v{__version__}
> Re-generate with: `dobladillo skill > SKILL.md`

A scriptable toolchain for DNA origami bricks: design a structure, check it
against the design rules, produce what the lab needs to order and fold it,
bundle an oxDNA job, and turn a finished run into observables that have
experimental counterparts.

## Available commands

{commands}

Every command accepts `--json`. Start with `dobladillo describe --json`, which
emits the whole surface with options, types and defaults.

{SKILL_DISCIPLINE}
## Where things are

- `docs/DESIGN.md` — the design document: what this is for and why.
- `docs/STATUS.md` — roadmap state and known gaps.
- `docs/PIPELINE.md` — how design, simulation, assembly, imaging and analysis fit.
- `AGENTS.md` — the same working rules, in the repository.
"""


@app.command("skill")
def skill() -> None:
    """Print a SKILL.md for this tool, generated from its own commands."""
    typer.echo(_skill_markdown(), nl=False)


if __name__ == "__main__":
    app()

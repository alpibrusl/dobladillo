"""The MCP server: E1's analysis end to end through tools alone, refusals
arriving with their kind, and no tool that passes a human gate.

The stdio round trip matters on its own. In-process calls cannot catch the
failure unique to stdio -- anything printed to stdout corrupts the protocol
stream -- so one test talks to a real server process through the SDK's own
client.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mcp")

import anyio  # noqa: E402  (installed with the mcp extra)

from dobladillo import mcp_server  # noqa: E402
from dobladillo.experiments import scaffold  # noqa: E402


def _call(server, tool: str, **arguments):
    return anyio.run(server.call_tool, tool, arguments)


def _payload(result) -> dict:
    return result.structured_content or json.loads(result.content[0].text)


def _e1_like_folder(root: Path, *, tip_measured: bool) -> Path:
    """An experiment folder with synthetic scans of a known rectangle -- the
    same dry run E1's protocol was walked through."""
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan
    from dobladillo.parts.rectangle import rothemund_rectangle

    dims = sorted(rothemund_rectangle().as_dict()["approx_dimensions_nm"].values(), reverse=True)
    prediction = {
        "part": "rectangle",
        "predicted_nm": {"length": dims[0], "width": dims[-1], "height": 2.0},
    }
    directory = scaffold(root, slug="e1", prediction=prediction, plan="# p\n", protocol="# p\n")
    for i in range(3):
        scan = synthetic_scan(seed=i, length_nm=dims[0], width_nm=dims[-1], n_aggregates=0)
        write_gsf(scan.image, directory / "during" / "raw" / f"scan-{i}.gsf")
    if tip_measured:
        instrument = json.loads((directory / "during" / "instrument.json").read_text())
        instrument["tip"]["measured_radius_before_nm"] = 10.0
        instrument["tip"]["measured_radius_after_nm"] = 10.0
        (directory / "during" / "instrument.json").write_text(json.dumps(instrument))
    return directory


def test_no_tool_passes_a_human_gate() -> None:
    """Ordering and pre-registration are the experimentalist's. The strongest
    way to keep an agent from doing them is for no tool to exist."""
    server = mcp_server.create_server(Path("."))
    names = {t.name for t in anyio.run(server.list_tools)}
    source = inspect.getsource(mcp_server.create_server)
    for command in mcp_server.FORBIDDEN_COMMANDS:
        words = command.split()
        assert "_".join(words) not in names
        assert ", ".join(f'"{w}"' for w in words) not in source, command
    assert not any("order" in n for n in names)


def test_e1_analysis_runs_end_to_end_through_tools(tmp_path: Path) -> None:
    _e1_like_folder(tmp_path, tip_measured=True)
    server = mcp_server.create_server(tmp_path)

    listed = _payload(_call(server, "experiment_list"))
    assert listed["experiments"] == ["e1"]

    check = _call(server, "experiment_check", name="e1")
    assert not check.is_error, check

    report = _call(server, "experiment_report", name="e1")
    assert not report.is_error, report
    measured = json.loads((tmp_path / "e1" / "post" / "measurements.json").read_text())
    assert len(measured["scans"]) == 3


def test_a_missing_tip_radius_arrives_as_a_structured_refusal(tmp_path: Path) -> None:
    """The refusal the whole experiment layout exists for, crossing the MCP
    boundary intact: an error, with the kind an agent can branch on."""
    _e1_like_folder(tmp_path, tip_measured=False)
    server = mcp_server.create_server(tmp_path)
    result = _call(server, "experiment_report", name="e1")
    assert result.is_error
    assert _payload(result)["error"]["kind"] == "no_tip_radius"
    assert not (tmp_path / "e1" / "post" / "measurements.json").exists()


def test_a_path_outside_the_root_is_refused(tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    server = mcp_server.create_server(tmp_path / "root")
    result = _call(server, "experiment_check", name="../../etc")
    assert result.is_error
    assert _payload(result)["error"]["kind"] == "outside_root"


def test_design_tools_answer(tmp_path: Path) -> None:
    server = mcp_server.create_server(tmp_path)
    assert _payload(_call(server, "build_part", part="rectangle"))["staple_count"] == 220
    lint = _payload(_call(server, "lint_part", part="rectangle"))
    assert lint["ok"] is True
    shape = _payload(_call(server, "predict_shape", part="bundle"))
    assert shape["valid"] is True and shape["straight"] is True
    unknown = _call(server, "lint_part", part="teapot")
    assert unknown.is_error and _payload(unknown)["error"]["kind"] == "unknown_part"


def test_a_real_stdio_session(tmp_path: Path) -> None:
    """A separate server process, spoken to by the SDK's client. Fails if
    anything the tools run writes to stdout."""
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    _e1_like_folder(tmp_path, tip_measured=False)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dobladillo.cli", "mcp", "--root", str(tmp_path)],
    )

    async def session() -> tuple[set[str], object]:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            tools = {t.name for t in (await client.list_tools()).tools}
            refused = await client.call_tool("experiment_report", {"name": "e1"})
            return tools, refused

    tools, refused = anyio.run(session)
    assert {"experiment_report", "queue_status", "lint_part"} <= tools
    assert refused.is_error
    assert "no_tip_radius" in refused.content[0].text


def test_compare_arms_refuses_through_mcp_without_the_record(tmp_path: Path) -> None:
    """E2's command, reached by an agent: an empty record is a refusal with a
    kind, never a comparison against guessed tip radii."""
    _e1_like_folder(tmp_path, tip_measured=False)
    server = mcp_server.create_server(tmp_path)
    result = _call(server, "experiment_compare_arms", name="e1")
    assert result.is_error
    assert _payload(result)["error"]["kind"].startswith("no_")


def test_lateral_calibration_runs_through_the_tool(tmp_path: Path) -> None:
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic_calibration import calibration_scan
    from dobladillo.parts.calibration_tile import calibration_tile

    tile = calibration_tile()
    names = []
    for k in range(2):
        scan = calibration_scan(
            tile.marks_nm,
            sheet_nm=tile.sheet_nm,
            n_tiles=20,
            seed=90 + k,
            scale_x=1.04,
            scale_y=0.98,
            skew_deg=1.0,
            anisotropy=1.05,
        )
        write_gsf(scan.image, tmp_path / f"tile-{k}.gsf")
        names.append(f"tile-{k}.gsf")
    server = mcp_server.create_server(tmp_path)
    result = _call(server, "calibrate_lateral", scans=names)
    assert not result.is_error, result
    scanner = _payload(result)["scanner"]
    assert abs(scanner["scale_x"]["value"] - 1.04) <= scanner["scale_x"]["U_k2"]


def test_calibration_tools_refuse_files_outside_the_root(tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    (tmp_path / "outside.gsf").write_text("not a scan")
    server = mcp_server.create_server(tmp_path / "root")
    result = _call(server, "calibrate_tip", scan="../outside.gsf")
    assert result.is_error
    assert _payload(result)["error"]["kind"] == "outside_root"


def test_calibration_report_runs_through_the_tool_and_writes_post(tmp_path: Path) -> None:
    """A K folder, by name: the tool writes post/calibration.json as
    experiment_report writes post/, and never anything under during/raw/."""
    from typer.testing import CliRunner

    from dobladillo.calibration.tip import dilate, paraboloid_tip
    from dobladillo.cli import app
    from dobladillo.imaging.heightmap import HeightMap
    from dobladillo.imaging.readers import write_gsf

    result = CliRunner().invoke(
        app, ["experiment", "new", "k4", "--part", "calibration-tile", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    directory = tmp_path / "k4"
    surface = np.zeros((128, 128))
    for i, j in ((30, 40), (90, 70), (60, 100)):
        surface[i, j] = 30.0
    image = dilate(surface, paraboloid_tip(10.0, 1.0, 31))
    raw = directory / "during" / "raw" / "staircase"
    raw.mkdir()
    write_gsf(HeightMap(image, 1.0, "synthetic"), raw / "S1-01.gsf")
    before = sorted(p.name for p in raw.iterdir())

    server = mcp_server.create_server(tmp_path)
    refused = _call(server, "calibrate_report", name="k4")
    assert refused.is_error
    assert _payload(refused)["error"]["kind"] == "no_scan_direction"

    path = directory / "during" / "instrument.json"
    instrument = json.loads(path.read_text())
    instrument["scan"]["direction"] = "trace"
    instrument["tip"]["part_number"] = "synthetic"
    path.write_text(json.dumps(instrument))
    result = _call(server, "calibrate_report", name="k4")
    assert not result.is_error, result
    written = json.loads((directory / "post" / "calibration.json").read_text())
    assert written["analyses"]["tip"]["results"][0]["block"] == "S1"
    assert sorted(p.name for p in raw.iterdir()) == before


def test_calibration_report_refuses_a_folder_outside_the_root(tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    server = mcp_server.create_server(tmp_path / "root")
    result = _call(server, "calibrate_report", name="../")
    assert result.is_error
    assert _payload(result)["error"]["kind"] == "outside_root"

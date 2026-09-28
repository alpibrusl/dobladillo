"""The provenance chain, from design through prediction, order and scan to comparison.

Each test that says a mismatch is caught has a partner saying the matching
case passes, because a check that fires on everything proves as little as one
that fires on nothing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo import provenance as pv
from dobladillo.cli import app
from dobladillo.experiments import check, scaffold
from dobladillo.parts.bundle import six_helix_bundle
from dobladillo.parts.rectangle import rothemund_rectangle

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def _cli(*args: str):
    return runner.invoke(app, list(args))


# --------------------------------------------------------------- the design


def test_the_design_hash_is_reproducible_and_tells_parts_apart() -> None:
    a = pv.design_sha256(rothemund_rectangle().design)
    assert a == pv.design_sha256(rothemund_rectangle().design)
    assert a != pv.design_sha256(six_helix_bundle().design)
    assert len(a) == 64


def test_ordering_a_design_does_not_change_its_identity() -> None:
    """Plate and well labels are attached when the design is ORDERED. If they
    counted, the design in pre/order would never match the one predicted."""
    from dobladillo.lab import plates as lab

    design = rothemund_rectangle().design
    before = pv.design_sha256(design)
    lab.name_and_assign_wells(design, plate_type=96)
    assert pv.design_sha256(design) == before
    # ...and the labels really were attached, so the test is not vacuous.
    assert any(s.name for s in design.strands)


def test_one_changed_base_changes_the_hash() -> None:
    """The negative control for everything the canonical form leaves out."""
    design = rothemund_rectangle().design
    before = pv.design_sha256(design)
    staple = next(s for s in design.strands if not s.is_scaffold)
    domain = staple.domains[0]
    sequence = domain.dna_sequence
    domain.dna_sequence = ("A" if sequence[0] != "A" else "C") + sequence[1:]
    assert pv.design_sha256(design) != before


def test_the_hash_is_of_the_design_not_of_the_file(tmp_path: Path) -> None:
    """Two .sc files of one design differ byte for byte with whoever wrote
    them. The hash of either is the design's."""
    design = rothemund_rectangle().design
    design.write_scadnano_file(directory=str(tmp_path), filename="a.sc")
    original = tmp_path / "a.sc"
    data = json.loads(original.read_text())
    data["version"] = "0.0.0-some-other-writer"
    reformatted = tmp_path / "b.sc"
    reformatted.write_text(json.dumps(data, indent=7))

    assert pv.file_sha256(original) != pv.file_sha256(reformatted)
    assert pv.design_file_sha256(original) == pv.design_sha256(design)
    assert pv.design_file_sha256(reformatted) == pv.design_sha256(design)


def test_the_prediction_hash_ignores_only_the_gate() -> None:
    prediction = {"part": "x", "predicted_nm": {"length": 100.0}, "gate": {"criterion": ""}}
    gated = {**prediction, "gate": {"criterion": "fails if length > 120 nm"}}
    moved = {**prediction, "predicted_nm": {"length": 101.0}}
    assert pv.prediction_sha256(prediction) == pv.prediction_sha256(gated)
    assert pv.prediction_sha256(prediction) != pv.prediction_sha256(moved)


# ---------------------------------------------------------- the simulation


def test_a_bundle_names_its_design_and_its_topology(tmp_path: Path) -> None:
    from dobladillo.analysis.runs import check_run
    from dobladillo.sim.jobs import write_job_bundle

    design = six_helix_bundle().design
    job = write_job_bundle(design, directory=tmp_path, name="b", part="bundle", test_mode=True)
    recorded = job.metadata["provenance"]
    assert recorded["design_sha256"] == pv.design_sha256(design)
    assert recorded["files"]["topology"] == pv.file_sha256(tmp_path / "b.top")

    assert not any("topology file changed" in p for p in check_run(tmp_path).problems)
    top = tmp_path / "b.top"
    top.write_text(top.read_text() + "\n")
    assert any("topology file changed" in p for p in check_run(tmp_path).problems)


def _finished_run(directory: Path, *, design_hash: str | None) -> Path:
    """A bundle dressed as a finished run: enough to reach the design check."""
    from dobladillo.analysis.runs import STAGES
    from dobladillo.sim.jobs import write_job_bundle

    write_job_bundle(
        six_helix_bundle().design, directory=directory, name="b", part="bundle", test_mode=True
    )
    for stage in STAGES:
        (directory / f"conf_{stage}.dat").write_text("")
    shutil.copy(directory / "b.dat", directory / "traj_04_production.dat")
    meta = json.loads((directory / "metadata.json").read_text())
    meta["test_mode"] = False
    if design_hash is None:
        del meta["provenance"]
    else:
        meta["provenance"]["design_sha256"] = design_hash
    (directory / "metadata.json").write_text(json.dumps(meta))
    return directory


def test_compare_refuses_a_run_of_another_design(tmp_path: Path) -> None:
    run = _finished_run(tmp_path / "other", design_hash="0" * 64)
    result = _cli("compare", "bundle", "--run", str(run), "--tip-radius", "10", "--json")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "design_mismatch"


def test_compare_accepts_a_run_of_the_same_design(tmp_path: Path) -> None:
    run = _finished_run(tmp_path / "same", design_hash=pv.design_sha256(six_helix_bundle().design))
    result = _cli("compare", "bundle", "--run", str(run), "--tip-radius", "10", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["sources"]["simulated"]


def test_compare_says_so_when_a_run_predates_the_record(tmp_path: Path) -> None:
    run = _finished_run(tmp_path / "old", design_hash=None)
    result = _cli("compare", "bundle", "--run", str(run), "--tip-radius", "10")
    assert "design_mismatch" not in result.output
    assert "records no design hash" in result.output


# ----------------------------------------------------- the experiment folder


@pytest.fixture(scope="module")
def fresh(tmp_path_factory) -> Path:
    """One `experiment new`, copied per test: it builds and orders a part."""
    root = tmp_path_factory.mktemp("experiments")
    result = _cli(
        "experiment", "new", "2026-10-01-x", "--part", "twist-corrected", "--root", str(root)
    )
    assert result.exit_code == 0, result.output
    return root / "2026-10-01-x"


@pytest.fixture
def folder(fresh: Path, tmp_path: Path) -> Path:
    target = tmp_path / fresh.name
    shutil.copytree(fresh, target)
    return target


def test_experiment_new_records_every_link(folder: Path) -> None:
    from dobladillo.parts.twist_pair import twist_pair

    expected = pv.design_sha256(twist_pair().corrected.design)
    prediction = json.loads((folder / "pre" / "prediction.json").read_text())
    assert prediction["provenance"]["design_sha256"] == expected

    record = json.loads((folder / "pre" / "provenance.json").read_text())
    assert record["design"]["sha256"] == expected
    assert record["prediction"]["sha256"] == pv.prediction_sha256(prediction)

    manifest = json.loads((folder / "pre" / "order" / "twist-corrected_manifest.json").read_text())
    assert manifest["design_sha256"] == expected
    assert "pipetting.json" in manifest["files"]

    report = check(folder)
    # A fresh folder is complete but for the one line only a person writes.
    assert [p for p in report.problems if "gate is not written" not in p] == []
    assert report.chain.verified
    assert [link.node for link in report.chain.links] == [
        "design",
        "prediction",
        "order",
        "experiment folder",
    ]


def test_a_re_tiled_order_is_a_mismatch_and_the_report_refuses(folder: Path) -> None:
    """What happened to E1 and E2, made visible: the oligos were regenerated
    from a new design after the prediction was written."""
    order = folder / "pre" / "order"
    for path in order.iterdir():
        path.unlink()
    result = _cli("lab", "order", "twist-uncorrected", "--out", str(order), "--json")
    assert result.exit_code == 0, result.output

    report = check(folder)
    assert any("is not what was predicted" in p for p in report.problems)
    assert not report.chain.verified

    (folder / "during" / "raw" / "s.gsf").write_text("not read: refused first")
    result = _cli("experiment", "report", str(folder), "--json")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "design_mismatch"


def test_an_order_file_edited_after_its_manifest_breaks_the_chain(folder: Path) -> None:
    bulk = next((folder / "pre" / "order").glob("*_bulk.csv"))
    bulk.write_text(bulk.read_text() + "extra,ACGT\n")
    report = check(folder)
    assert any("changed since" in p for p in report.problems)
    assert report.chain.scan_design is None

    (folder / "during" / "raw" / "s.gsf").write_text("x")
    result = _cli("experiment", "report", str(folder), "--json")
    assert json.loads(result.stdout)["error"]["kind"] == "provenance_incomplete"


def test_editing_the_prediction_is_seen_but_filling_the_gate_is_not(folder: Path) -> None:
    path = folder / "pre" / "prediction.json"
    prediction = json.loads(path.read_text())
    prediction["gate"]["criterion"] = "fails if under half the particles lie flat"
    path.write_text(json.dumps(prediction, indent=2))
    assert check(folder).problems == ()

    prediction["predicted_nm"]["length"] += 5
    path.write_text(json.dumps(prediction, indent=2))
    assert any("has changed since" in p for p in check(folder).problems)


def test_a_full_report_hashes_every_scan_and_names_its_design(folder: Path) -> None:
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan

    predicted = json.loads((folder / "pre" / "prediction.json").read_text())["predicted_nm"]
    for i in range(2):
        scan = synthetic_scan(
            seed=i, length_nm=predicted["length"], width_nm=predicted["width"], n_aggregates=0
        )
        write_gsf(scan.image, folder / "during" / "raw" / f"scan-{i}.gsf")
    instrument_path = folder / "during" / "instrument.json"
    instrument = json.loads(instrument_path.read_text())
    instrument["tip"]["measured_radius_before_nm"] = 10.0
    instrument_path.write_text(json.dumps(instrument))

    result = _cli("experiment", "report", str(folder), "--json")
    assert result.exit_code == 0, result.output
    chain = json.loads((folder / "post" / "comparison.json").read_text())["provenance"]
    design = chain["design_sha256"]
    assert chain["verified"]
    assert chain["scan_design_sha256"] == design
    assert len(chain["scans"]) == 2
    for scan in chain["scans"]:
        assert scan["parent"] == design
        assert scan["sha256"] == pv.file_sha256(folder / scan["name"])
    assert "chain VERIFIED" in (folder / "post" / "report.md").read_text()


# ------------------------------------------------------------ legacy records


def test_a_legacy_folder_is_a_record_problem_not_a_crash(tmp_path: Path) -> None:
    directory = scaffold(
        tmp_path,
        slug="old",
        prediction={"part": "rectangle", "predicted_nm": {"length": 1.0, "width": 1.0}},
        plan="# p\n",
        protocol="# p\n",
    )
    assert not (directory / "pre" / "provenance.json").exists()
    report = check(directory)
    assert report.chain.legacy
    assert any(p.startswith("no design hash recorded") for p in report.problems)


@pytest.mark.parametrize("folder_name", ["2026-09-22-rectangle-afm", "2026-09-23-twist-pair"])
def test_the_committed_experiments_are_reported_as_legacy_and_left_alone(
    folder_name: str,
) -> None:
    """E1 and E2 were re-tiled after their predictions were written. Nothing
    may be added to those predictions; the record problem is the finding."""
    directory = ROOT / "experiments" / folder_name
    prediction = json.loads((directory / "pre" / "prediction.json").read_text())
    assert "provenance" not in prediction
    assert not (directory / "pre" / "provenance.json").exists()
    problems = check(directory).problems
    assert any("no design hash recorded" in p and "RETILED.md" in p for p in problems)


# --------------------------------------------------------------- dashboard


def test_the_dashboard_shows_the_chain(folder: Path, tmp_path: Path) -> None:
    from dobladillo.dashboard import gather, render

    legacy_root = tmp_path / "legacy"
    scaffold(
        legacy_root,
        slug="old",
        prediction={"part": "rectangle", "predicted_nm": {"length": 1.0, "width": 1.0}},
        plan="# p\n",
        protocol="# p\n",
    )
    shutil.copytree(folder, legacy_root / folder.name)
    state = gather(experiments_root=legacy_root, runs_root=tmp_path / "no-runs")
    by_name = {f["name"]: f for f in state.folders}
    assert by_name["old"]["provenance"]["legacy"]
    fresh_chain = by_name[folder.name]["provenance"]
    assert fresh_chain["verified"]

    page = render(state)
    assert "no design hash recorded" in page
    assert f"design {fresh_chain['design_sha256'][:8]}" in page
    assert "chain holds" in page
    rectangle = next(p for p in state.parts if p.name == "rectangle")
    assert rectangle.design_sha256[:8] in page


def test_the_dashboard_flags_a_run_of_another_design(tmp_path: Path) -> None:
    from dobladillo.dashboard import gather, render

    runs = tmp_path / "runs"
    (runs / "bundle").mkdir(parents=True)
    (runs / "bundle" / "metadata.json").write_text(
        json.dumps({"provenance": {"design_sha256": "f" * 64}})
    )
    (runs / "rectangle").mkdir()
    (runs / "rectangle" / "metadata.json").write_text(
        json.dumps(
            {"provenance": {"design_sha256": pv.design_sha256(rothemund_rectangle().design)}}
        )
    )
    state = gather(experiments_root=tmp_path / "none", runs_root=runs)
    parts = {p.name: p for p in state.parts}
    assert parts["bundle"].run_matches is False
    assert parts["rectangle"].run_matches is True
    assert parts["hinge"].run_matches is None
    page = render(state)
    assert "run: design ffffffff" in page
    assert "run: same design" in page

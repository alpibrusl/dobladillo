"""The local export archive: Nanobase's layout, validated, never uploaded.

The validator is only worth having if it can fail, so most of this file is
negative controls: each one breaks a valid archive in exactly one way and
checks that the validator names that way.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dobladillo import provenance as pv
from dobladillo.cli import app
from dobladillo.export import CATEGORIES, ENTRY_FILE, LAYOUT, export_part, validate
from dobladillo.parts.bundle import six_helix_bundle
from dobladillo.parts.rectangle import rothemund_rectangle

runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def _cli(*args: str):
    return runner.invoke(app, list(args))


@pytest.fixture(scope="module")
def archive(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("export")
    part = rothemund_rectangle()
    result = export_part(part="rectangle", design=part.design, info=part.as_dict(), out=out)
    assert result.valid, result.problems
    return result.path


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


def _rewrite(src: Path, dst: Path, mutate: Callable[[dict[str, bytes]], None]) -> Path:
    members = _members(src)
    mutate(members)
    with zipfile.ZipFile(dst, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return dst


def _entry(members: dict[str, bytes]) -> dict:
    return json.loads(members[f"rectangle/{ENTRY_FILE}"])


def _set_entry(members: dict[str, bytes], entry: dict) -> None:
    members[f"rectangle/{ENTRY_FILE}"] = json.dumps(entry).encode()


# --------------------------------------------------------------- positive


def test_the_archive_holds_what_nanobase_asks_for(archive: Path) -> None:
    names = set(_members(archive))
    assert names == {
        "rectangle/entry.json",
        "rectangle/structure_designs/rectangle.sc",
        "rectangle/structure_designs/rectangle.json",
        "rectangle/oxdna/rectangle.top",
        "rectangle/oxdna/rectangle.dat",
        "rectangle/images/rectangle-strands.png",
    }
    entry = _entry(_members(archive))
    assert entry["layout"] == LAYOUT
    assert set(entry["files"]) == set(CATEGORIES)
    assert entry["structure"]["molecule_type"] == "DNA"
    assert "never uploads" in entry["never_uploaded"]
    # Nothing a person decides is decided here.
    assert all(entry["publication"][k] is None for k in ("doi", "citation", "licence", "patents"))
    assert entry["structure"]["applications"] == []


def test_the_design_file_is_the_design_the_provenance_names(archive: Path, tmp_path: Path) -> None:
    sc_file = tmp_path / "r.sc"
    sc_file.write_bytes(_members(archive)["rectangle/structure_designs/rectangle.sc"])
    expected = pv.design_sha256(rothemund_rectangle().design)
    assert pv.design_file_sha256(sc_file) == expected
    assert _entry(_members(archive))["provenance"]["design_sha256"] == expected


def test_exporting_twice_gives_the_same_bytes(archive: Path, tmp_path: Path) -> None:
    """Fixed timestamps and an unstamped PNG: the archive's hash means something."""
    part = rothemund_rectangle()
    again = export_part(part="rectangle", design=part.design, info=part.as_dict(), out=tmp_path)
    assert again.sha256 == pv.file_sha256(archive)


def test_a_format_that_cannot_hold_the_design_is_explained_not_faked(tmp_path: Path) -> None:
    """The hinge's latches are extensions, which caDNAno v2 cannot express."""
    result = _cli("export", "hinge", "--out", str(tmp_path), "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["valid"]
    assert payload["uploaded"] is False
    assert "caDNAno v2" in payload["not_included"]["cadnano_v2"]
    assert payload["files"]["structure_designs"] == 1


# ------------------------------------------------------- negative controls


def _problems_after(archive: Path, tmp_path: Path, mutate) -> list[str]:
    return validate(_rewrite(archive, tmp_path / "broken.zip", mutate))


def test_a_valid_archive_has_no_problems(archive: Path, tmp_path: Path) -> None:
    """The control for the controls: a byte-for-byte rewrite still validates."""
    assert _problems_after(archive, tmp_path, lambda m: None) == []


def test_a_changed_file_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        m["rectangle/oxdna/rectangle.top"] += b"\n"

    problems = _problems_after(archive, tmp_path, mutate)
    assert any("rectangle.top does not match its recorded sha256" in p for p in problems)


def test_an_unlisted_file_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        m["rectangle/images/extra.png"] = b"x"

    problems = _problems_after(archive, tmp_path, mutate)
    assert any("images/extra.png is in the archive but not listed" in p for p in problems)


def test_a_missing_design_file_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        del m["rectangle/structure_designs/rectangle.sc"]
        entry = _entry(m)
        entry["files"]["structure_designs"] = [
            r for r in entry["files"]["structure_designs"] if not r["path"].endswith(".sc")
        ]
        _set_entry(m, entry)

    problems = _problems_after(archive, tmp_path, mutate)
    assert any("no original design file" in p for p in problems)


def test_a_design_file_of_another_design_is_caught(archive: Path, tmp_path: Path) -> None:
    """Hashes all consistent, the wrong object inside: only the design hash sees it."""
    other = tmp_path / "other"
    six_helix_bundle().design.write_scadnano_file(directory=str(other), filename="b.sc")
    data = (other / "b.sc").read_bytes()

    def mutate(m):
        m["rectangle/structure_designs/rectangle.sc"] = data
        entry = _entry(m)
        for record in entry["files"]["structure_designs"]:
            if record["path"].endswith(".sc"):
                record["sha256"] = pv.sha256_bytes(data)
                record["bytes"] = len(data)
        _set_entry(m, entry)

    problems = _problems_after(archive, tmp_path, mutate)
    assert len(problems) == 1
    assert "but provenance names" in problems[0]


def test_a_missing_image_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        del m["rectangle/images/rectangle-strands.png"]
        entry = _entry(m)
        entry["files"]["images"] = []
        _set_entry(m, entry)

    assert any("no image" in p for p in _problems_after(archive, tmp_path, mutate))


def test_a_path_outside_the_entry_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        m["rectangle/../escape.txt"] = b"x"

    assert any("unsafe member path" in p for p in _problems_after(archive, tmp_path, mutate))


def test_a_filled_in_guess_of_a_molecule_type_is_caught(archive: Path, tmp_path: Path) -> None:
    def mutate(m):
        entry = _entry(m)
        entry["structure"]["molecule_type"] = "origami"
        _set_entry(m, entry)

    assert any("molecule_type" in p for p in _problems_after(archive, tmp_path, mutate))


def test_results_without_a_verified_chain_are_caught(archive: Path, tmp_path: Path) -> None:
    """The #13 rule at the last step: a comparison goes in only with its provenance."""
    body = b'{"agrees": true}'

    def mutate(m):
        m["rectangle/experimental_results/comparison.json"] = body
        entry = _entry(m)
        entry["files"]["experimental_results"] = [
            {
                "path": "experimental_results/comparison.json",
                "sha256": pv.sha256_bytes(body),
                "bytes": len(body),
            }
        ]
        _set_entry(m, entry)

    problems = _problems_after(archive, tmp_path, mutate)
    assert any("without a verified provenance chain" in p for p in problems)


def test_something_that_is_not_a_zip_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "x.zip"
    path.write_text("not a zip")
    assert validate(path)[0].startswith("not a readable zip")


def test_export_check_passes_and_fails_through_the_cli(archive: Path, tmp_path: Path) -> None:
    ok = _cli("export-check", str(archive), "--json")
    assert ok.exit_code == 0
    assert json.loads(ok.stdout)["valid"]

    broken = _rewrite(archive, tmp_path / "b.zip", lambda m: m.update({"rectangle/x": b"x"}))
    bad = _cli("export-check", str(broken), "--json")
    assert bad.exit_code != 0
    assert json.loads(bad.stdout)["problems"]

    missing = _cli("export-check", str(tmp_path / "nope.zip"), "--json")
    assert json.loads(missing.stdout)["error"]["kind"] == "missing_file"


# ------------------------------------------------------------- experiments


def test_a_legacy_experiment_is_refused(tmp_path: Path) -> None:
    """E1 records no design hash, and was re-tiled after its prediction."""
    folder = ROOT / "experiments" / "2026-09-22-rectangle-afm"
    result = _cli(
        "export", "rectangle", "--experiment", str(folder), "--out", str(tmp_path), "--json"
    )
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "provenance_unverified"
    assert not list(tmp_path.iterdir()), "a refused export must not leave an archive"


@pytest.fixture(scope="module")
def reported(tmp_path_factory) -> Path:
    """A new-style experiment of the corrected twist arm, with a finished report."""
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan

    root = tmp_path_factory.mktemp("experiments")
    result = _cli(
        "experiment", "new", "2026-10-02-y", "--part", "twist-corrected", "--root", str(root)
    )
    assert result.exit_code == 0, result.output
    folder = root / "2026-10-02-y"
    predicted = json.loads((folder / "pre" / "prediction.json").read_text())["predicted_nm"]
    scan = synthetic_scan(
        seed=0, length_nm=predicted["length"], width_nm=predicted["width"], n_aggregates=0
    )
    write_gsf(scan.image, folder / "during" / "raw" / "scan-0.gsf")
    instrument_path = folder / "during" / "instrument.json"
    instrument = json.loads(instrument_path.read_text())
    instrument["tip"]["measured_radius_before_nm"] = 10.0
    instrument_path.write_text(json.dumps(instrument))
    result = _cli("experiment", "report", str(folder), "--json")
    assert result.exit_code == 0, result.output
    return folder


def test_a_verified_experiment_goes_in_with_its_comparison(reported: Path, tmp_path: Path) -> None:
    result = _cli(
        "export", "twist-corrected", "--experiment", str(reported), "--out", str(tmp_path), "--json"
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["valid"]
    assert payload["files"]["experimental_results"] >= 3
    assert payload["files"]["experimental_protocols"] >= 4
    experiment = payload["provenance"]["experiment"]
    assert experiment["results_included"]
    assert experiment["comparison"]["verified"]
    assert experiment["comparison"]["design_sha256"] == payload["provenance"]["design_sha256"]


def test_an_experiment_of_another_part_is_refused(reported: Path, tmp_path: Path) -> None:
    result = _cli(
        "export", "rectangle", "--experiment", str(reported), "--out", str(tmp_path), "--json"
    )
    assert json.loads(result.stdout)["error"]["kind"] == "design_mismatch"


def test_an_unfinished_experiment_exports_its_protocols_only(
    reported: Path, tmp_path: Path
) -> None:
    folder = tmp_path / reported.name
    shutil.copytree(reported, folder)
    shutil.rmtree(folder / "post")
    (folder / "post").mkdir()
    result = _cli(
        "export", "twist-corrected", "--experiment", str(folder), "--out", str(tmp_path / "o"),
        "--json",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["files"]["experimental_results"] == 0
    assert payload["provenance"]["experiment"]["results_included"] is False

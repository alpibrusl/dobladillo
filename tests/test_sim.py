"""The bundle is checked for the things that would be silently wrong.

A job bundle that is subtly malformed does not fail loudly: it runs, produces a
trajectory, and that trajectory is then analysed as though it meant something.
The tests here target exactly those failure modes -- a wrong nucleotide
mapping, a trap written in only one direction, a stage reading the wrong
configuration, metadata that does not say what salt was used.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from dobladilo import _scadnano as ad
from dobladilo.parts.bundle import six_helix_bundle
from dobladilo.parts.rectangle import rothemund_rectangle
from dobladilo.sim.jobs import mutual_traps, write_job_bundle

COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    directory = tmp_path_factory.mktemp("job")
    return write_job_bundle(
        six_helix_bundle().design,
        directory=directory,
        name="b6hb",
        part="bundle",
        test_mode=True,
    )


# ----------------------------------------------------- the nucleotide mapping


@pytest.mark.parametrize(
    "part",
    [
        pytest.param(six_helix_bundle, id="bundle"),
        pytest.param(rothemund_rectangle, id="rectangle"),
    ],
)
def test_paired_nucleotides_hold_complementary_bases(part, tmp_path) -> None:
    """The mapping is verified against the file oxDNA will actually read.

    External forces address nucleotides by index, so a mapping that is off by
    even one would restrain the wrong pairs and quietly deform the structure
    during relaxation. Complementarity is the check that catches it: if the
    indices were wrong, paired positions would not hold complementary bases.
    The rectangle is included because deletions shift every index after them.
    """
    design = part().design
    files = ad.write_oxdna_files(design, directory=tmp_path, name="x")
    bases = ad.topology_bases(files["topology"])
    index = ad.nucleotide_indices(design)

    checked = 0
    for helix, offsets in design.base_pairs().items():
        for offset in offsets:
            a, b = index.get((helix, offset, True)), index.get((helix, offset, False))
            if a is None or b is None:
                continue
            assert COMPLEMENT[bases[a]] == bases[b], f"helix {helix} offset {offset}"
            checked += 1
    assert checked > 1000


def test_the_mapping_covers_every_nucleotide(tmp_path) -> None:
    design = rothemund_rectangle().design
    files = ad.write_oxdna_files(design, directory=tmp_path, name="x")
    index = ad.nucleotide_indices(design)
    assert sorted(index.values()) == list(range(len(ad.topology_bases(files["topology"]))))


# ------------------------------------------------------------------- traps


def test_every_trap_is_written_in_both_directions() -> None:
    """oxDNA's reference particle feels no force, so a one-way trap pulls one
    nucleotide towards a partner free to drift away from it."""
    text, pairs = mutual_traps(six_helix_bundle().design)
    blocks = re.findall(r"particle = (\d+)\nref_particle = (\d+)", text)
    assert len(blocks) == 2 * pairs
    directed = {(a, b) for a, b in blocks}
    assert all((b, a) in directed for a, b in directed)


def test_trap_indices_are_inside_the_structure(tmp_path) -> None:
    design = six_helix_bundle().design
    files = ad.write_oxdna_files(design, directory=tmp_path, name="x")
    total = len(ad.topology_bases(files["topology"]))
    text, _ = mutual_traps(design)
    assert all(0 <= int(n) < total for n in re.findall(r"particle = (\d+)", text))


def test_traps_hold_every_scaffold_base(bundle) -> None:
    """Anything less means part of the structure relaxes unrestrained."""
    assert bundle.trapped_pairs == 7056


# ------------------------------------------------------------------ bundle


def test_bundle_is_self_contained(bundle) -> None:
    """Every file a stage names must be in the directory, or on the machine
    that runs it the failure is a missing file halfway through."""
    present = {p.name for p in bundle.directory.iterdir()}
    for stage in ("01_mc", "02_md_trapped", "03_md_released", "04_production"):
        assert f"input_{stage}" in present
    assert {"b6hb.top", "b6hb.dat", "traps.txt", "run.sh", "metadata.json"} <= present


def test_stages_chain_through_their_configurations(bundle) -> None:
    """Stage n reads what stage n-1 wrote. A break here analyses the wrong run."""
    order = ["01_mc", "02_md_trapped", "03_md_released", "04_production"]
    produced = "b6hb.dat"
    for stage in order:
        text = (bundle.directory / f"input_{stage}").read_text()
        conf_in = re.search(r"^conf_file = (\S+)$", text, re.M).group(1)
        assert conf_in == produced, f"{stage} reads {conf_in}, not {produced}"
        produced = re.search(r"^lastconf_file = (\S+)$", text, re.M).group(1)


def test_only_the_trapped_stage_uses_external_forces(bundle) -> None:
    for stage in ("01_mc", "03_md_released", "04_production"):
        assert "external_forces = 0" in (bundle.directory / f"input_{stage}").read_text()
    trapped = (bundle.directory / "input_02_md_trapped").read_text()
    assert "external_forces = 1" in trapped
    assert "external_forces_file = traps.txt" in trapped


def test_production_runs_without_force_caps(bundle) -> None:
    """Caps are a relaxation aid. Left on, they act on the trajectory that
    gets analysed."""
    production = (bundle.directory / "input_04_production").read_text()
    assert "max_backbone_force" not in production
    for stage in ("01_mc", "02_md_trapped", "03_md_released"):
        assert "max_backbone_force = 5.0" in (bundle.directory / f"input_{stage}").read_text()


def test_every_stage_records_the_salt(bundle) -> None:
    """DNA2 requires it, and a prediction at one proxy salt is not comparable
    to one at another."""
    for stage in ("01_mc", "02_md_trapped", "03_md_released", "04_production"):
        text = (bundle.directory / f"input_{stage}").read_text()
        assert "salt_concentration = 0.5" in text
        assert "interaction_type = DNA2" in text


def test_metadata_says_the_simulation_has_not_run(bundle) -> None:
    """Producing a bundle is not evidence that anything was simulated."""
    meta = json.loads((bundle.directory / "metadata.json").read_text())
    assert meta["status"] == "not run"
    assert meta["model"]["salt_note"]
    assert meta["protocol"]["deviation_from_design_doc"]


def test_test_mode_says_its_output_is_not_a_result(bundle) -> None:
    assert bundle.metadata["test_mode"] is True
    assert "not a result" in bundle.metadata["owed_by_human"]


def test_test_mode_forces_cpu(bundle) -> None:
    """Short stages exist to prove the chain runs anywhere, GPU or not."""
    for stage in ("02_md_trapped", "04_production"):
        assert "backend = CPU" in (bundle.directory / f"input_{stage}").read_text()


def test_a_real_bundle_targets_the_gpu_and_says_what_is_owed(tmp_path) -> None:
    real = write_job_bundle(
        six_helix_bundle().design, directory=tmp_path, name="b", part="bundle", test_mode=False
    )
    assert "backend = CUDA" in (tmp_path / "input_04_production").read_text()
    assert "not executed" in real.metadata["owed_by_human"]


def test_run_script_refuses_without_oxdna(tmp_path) -> None:
    import subprocess

    write_job_bundle(
        six_helix_bundle().design, directory=tmp_path, name="b", part="bundle", test_mode=True
    )
    # A real PATH, since the script itself needs a shell; only OXDNA is made
    # to point at nothing. Emptying PATH would test that `sh` is missing.
    result = subprocess.run(
        ["sh", str(tmp_path / "run.sh")],
        cwd=tmp_path,
        env={**os.environ, "OXDNA": "definitely-not-installed"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 127
    assert "oxDNA not found" in result.stderr


def test_bundle_rejects_an_unknown_backend(tmp_path) -> None:
    with pytest.raises(ValueError, match="CPU or CUDA"):
        write_job_bundle(
            six_helix_bundle().design, directory=tmp_path, name="b", part="bundle", backend="Metal"
        )

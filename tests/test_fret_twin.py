"""The FRET twin (#15): data of known p(latched), and the chain that recovers it.

Stated tolerances, all on fixed seeds:

- single-molecule bursts (about 3000 doubly labelled): p within 0.02 and
  within three bootstrap errors; each state's E within 0.02;
- bulk plate (three reads per well, 0.3% read noise): p within 0.015;
- calibration: leakage and direct excitation within 5%, gamma within 3%.

And the negative controls: a wrong gamma biases bulk p and is caught, a
missing control well is refused, and E4's gate fails when the offset is
outside the ladder.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from dobladillo.hamiltonian.fret_estimate import (
    MAX_STOICHIOMETRY_GAP,
    estimate_bursts,
    estimate_plate,
    gamma_beta,
)
from dobladillo.hamiltonian.fret_synthetic import (
    Calibration,
    FretTruth,
    synthetic_bursts,
    synthetic_plate,
)

TRUE = Calibration()
P_VALUES = (0.05, 0.3, 0.5, 0.9)


@pytest.mark.parametrize("p", P_VALUES)
def test_bursts_recover_p_and_both_states(p: float) -> None:
    data = synthetic_bursts(seed=1, p_latched=p)
    est = estimate_bursts(data)
    assert abs(est.p_latched - p) <= 0.02
    assert abs(est.p_latched - p) <= 3 * est.p_stderr
    assert est.e_open == pytest.approx(0.25, abs=0.02)
    assert est.e_latched == pytest.approx(0.75, abs=0.02)
    assert est.gamma_consistent


def test_bursts_recover_the_calibration() -> None:
    c = estimate_bursts(synthetic_bursts(seed=3, p_latched=0.4), bootstrap=0).corrections
    assert c.fitted
    assert c.leakage == pytest.approx(TRUE.leakage, rel=0.05)
    assert c.direct_excitation == pytest.approx(TRUE.direct_excitation, rel=0.05)
    assert c.gamma == pytest.approx(TRUE.gamma, rel=0.03)
    assert c.background == pytest.approx(TRUE.background, rel=0.1)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_bulk_recovers_p(seed: int) -> None:
    samples = {f"s{i}": p for i, p in enumerate(P_VALUES)}
    estimates = estimate_plate(synthetic_plate(seed=seed, samples=samples))
    for name, p in samples.items():
        assert abs(estimates[name].p_latched - p) <= 0.015, (name, estimates[name].as_dict())
        assert estimates[name].gamma_consistent


def test_bulk_calibration_matches_what_was_put_in() -> None:
    est = estimate_plate(synthetic_plate(seed=0, samples={"x": 0.5}))["x"]
    c = est.corrections
    assert c.leakage == pytest.approx(TRUE.leakage, rel=0.05)
    assert c.direct_excitation == pytest.approx(TRUE.direct_excitation, rel=0.05)
    assert c.gamma == pytest.approx(TRUE.gamma, rel=0.03)
    assert c.beta == pytest.approx(TRUE.beta, rel=0.03)


# ------------------------------------------------------- negative controls


def test_a_wrong_gamma_biases_bulk_p_and_is_detected() -> None:
    """The failure STAGES_0_AND_1.md warns about. Bulk E is linear in p only
    with gamma right; 30% off, p = 0.5 reads 0.46, and the locked references
    no longer share a stoichiometry."""
    plate = synthetic_plate(seed=0, samples={"x": 0.5})
    right = estimate_plate(plate, gamma=TRUE.gamma, beta=TRUE.beta)["x"]
    wrong = estimate_plate(plate, gamma=1.3 * TRUE.gamma, beta=TRUE.beta)["x"]
    assert abs(right.p_latched - 0.5) <= 0.015
    assert abs(wrong.p_latched - 0.5) > 0.02
    assert right.gamma_consistent
    assert not wrong.gamma_consistent
    assert wrong.stoichiometry_gap > MAX_STOICHIOMETRY_GAP


def test_a_wrong_gamma_moves_single_molecule_e_but_not_the_count() -> None:
    """Counting molecules into two states needs no gamma; their E does."""
    data = synthetic_bursts(seed=1, p_latched=0.5)
    right = estimate_bursts(data, gamma=TRUE.gamma, beta=TRUE.beta, bootstrap=0)
    wrong = estimate_bursts(data, gamma=1.3 * TRUE.gamma, beta=TRUE.beta, bootstrap=0)
    assert wrong.p_latched == pytest.approx(right.p_latched, abs=1e-9)
    assert abs(wrong.e_latched - 0.75) > 0.03
    assert right.gamma_consistent and not wrong.gamma_consistent


def test_the_estimator_never_reads_the_truth() -> None:
    data = synthetic_bursts(seed=5, p_latched=0.3)
    lied = dataclasses.replace(
        data, truth=FretTruth(p_latched=0.99, e_open=0.0, e_latched=1.0, calibration=TRUE)
    )
    a = estimate_bursts(data, bootstrap=0)
    b = estimate_bursts(lied, bootstrap=0)
    assert a.p_latched == b.p_latched


def test_a_plate_without_its_controls_is_refused() -> None:
    plate = synthetic_plate(seed=0, samples={"x": 0.5})
    del plate.wells["locked_latched"]
    with pytest.raises(ValueError, match="control wells"):
        estimate_plate(plate)


def test_gamma_needs_two_different_populations() -> None:
    with pytest.raises(ValueError, match="too close"):
        gamma_beta([(0.4, 0.5), (0.42, 0.5)])


def test_generators_are_deterministic_in_their_seed() -> None:
    a = synthetic_bursts(seed=7, p_latched=0.5)
    b = synthetic_bursts(seed=7, p_latched=0.5)
    c = synthetic_bursts(seed=8, p_latched=0.5)
    assert np.array_equal(a.bursts.da, b.bursts.da)
    assert not np.array_equal(a.bursts.da, c.bursts.da)
    assert a.conditions["synthetic"] is True
    assert a.conditions["seed"] == 7


def test_the_truth_is_what_was_asked_for() -> None:
    """The twin's own honesty: species drawn in the requested proportions."""
    data = synthetic_bursts(seed=2, p_latched=0.3, n_bursts=20000)
    species = np.array(data.truth.species)
    fret = species[(species == "open") | (species == "latched")]
    assert (fret == "latched").mean() == pytest.approx(0.3, abs=0.01)
    assert (species == "donor_only").mean() == pytest.approx(0.10, abs=0.01)


# ------------------------------------------------------- E4, end to end

SCRIPT = Path(__file__).resolve().parent.parent / "experiments" / "protocols" / "e4_dryrun.py"


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("e4_dryrun", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("offset", [5.0, 20.0, 35.0])
def test_e4_dry_run_recovers_the_offset(offset: float, tmp_path: Path) -> None:
    """E4 end to end on synthetic data, as E1 and E2 were: ladder, plate,
    calibration, p per rung, the gate, and the offset it locates."""
    out = tmp_path / "e4.json"
    assert _script().main(["--offset-kt", str(offset), "--seed", "0", "--out", str(out)]) == 0
    result = json.loads(out.read_text())
    assert result["synthetic"] is True
    assert result["gate_passed"] is True
    informative = [r for r in result["rungs"] if r["informative"]]
    assert informative
    for rung in informative:
        assert abs(rung["offset_kt"] - offset) <= max(3 * rung["offset_stderr_kt"], 0.3)
        assert abs(rung["p_measured"] - rung["p_true"]) <= 0.015


def test_e4_gate_fails_when_the_offset_is_out_of_reach(tmp_path: Path) -> None:
    out = tmp_path / "e4.json"
    assert _script().main(["--offset-kt", "60", "--out", str(out)]) == 0
    result = json.loads(out.read_text())
    assert result["gate_passed"] is False
    assert "joint length" in result["verdict"]


def test_e4_refuses_a_verdict_on_a_wrong_gamma(tmp_path: Path) -> None:
    out = tmp_path / "e4.json"
    assert _script().main(["--offset-kt", "20", "--gamma", "1.0", "--out", str(out)]) == 2
    result = json.loads(out.read_text())
    assert result["gate_passed"] is False
    assert result["verdict"].startswith("REFUSED")

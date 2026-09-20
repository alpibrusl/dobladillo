"""The construct series, and the arithmetic that decides whether they happen."""

from __future__ import annotations

from dobladilo.hamiltonian.experiments import (
    STAGE0_SCATTER_GATE_KT,
    all_series,
    stage0,
    stage1,
)


def test_stage_zero_sweeps_length_and_composition_separately() -> None:
    """Swept together they would be unattributable: a change in dG could be
    either, and the stage exists to tell them apart."""
    varies = [c.varies for c in stage0().constructs]
    lengths = {v["latch_bp"] for v in varies if "gc_fraction" not in v}
    gc_at = {v["latch_bp"] for v in varies if "gc_fraction" in v}
    assert len(lengths) >= 5
    assert gc_at == {8}  # the composition axis is swept at one fixed length


def test_the_scatter_gate_is_tighter_than_the_source_document() -> None:
    """A change made on this project's own measurement rather than on the
    document's estimate: at 1 kT of scatter a designed 1 kT coupling returns
    0.85 kT out, and Stage 1 then cannot meet its own criterion."""
    assert STAGE0_SCATTER_GATE_KT < 1.0
    assert any("TIGHTER" in note for note in stage0().notes)


def test_stage_one_puts_the_full_bias_grid_on_one_mechanism() -> None:
    """Full factorial is 54 constructs. The document asks for about twenty, so
    the grid is complete only where it decides something."""
    series = stage1()
    per_mechanism: dict[str, int] = {}
    for construct in series.constructs:
        mechanism = construct.varies["mechanism"]
        per_mechanism[mechanism] = per_mechanism.get(mechanism, 0) + 1

    assert max(per_mechanism.values()) == 9  # the 3x3 grid, on one mechanism
    assert len(per_mechanism) == 6  # all six coupling variants present
    assert 20 <= len(series.constructs) <= 30


def test_stage_one_calibrates_the_joint_states_not_the_single_spins() -> None:
    """The control that this project's simulation changed. A per-spin ligation
    bias is algebraically a field shift and cannot corrupt J; only a joint-state
    bias can. Calibrating per-site efficiency is the wrong control."""
    controls = " ".join(stage1().controls)
    assert "FOUR joint states" in controls
    assert "CANNOT corrupt J" in controls


def test_stage_one_includes_an_uncoupled_control() -> None:
    """Any correlation measured with no strut is an artefact, and it sets the
    background |J| has to beat."""
    assert any("UNCOUPLED" in c for c in stage1().controls)


def test_equilibration_is_a_standing_control() -> None:
    """Section 6.3: subtle, and it would fool you if you were not looking."""
    assert any("two initial conditions" in c for c in stage1().controls)


def test_sharing_a_core_is_what_makes_the_series_affordable() -> None:
    """Not a nicety. Without it Stage 1 is a EUR 30k order instead of a EUR 4k
    one, which moves it from fundable to not."""
    for series in all_series():
        assert series.cost_eur < 0.25 * series.cost_without_sharing_eur


def test_both_stages_come_in_under_the_documents_budget() -> None:
    """Conditional on the core actually being shareable, which is a design
    constraint on the hinge and not a given."""
    assert stage0().cost_eur < 3000  # document says EUR 3-5k
    assert stage1().cost_eur < 8000  # document says EUR 8-12k

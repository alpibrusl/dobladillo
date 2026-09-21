"""The hinge: the first part whose prediction is a distribution, not a shape."""

from __future__ import annotations

import pytest
import scadnano as sc

from dobladillo import _scadnano as ad
from dobladillo.parts._lattice import SPAN_MULTIPLE_NT, pair_lower
from dobladillo.parts.hinge import DEFAULT_LATCH, bistable_hinge
from dobladillo.routing.rules import Severity, lint
from dobladillo.sequence.thermo import duplex, latch_field_kt, reverse_complement


@pytest.fixture(scope="module")
def hinge():
    return bistable_hinge()


def test_it_builds_and_accounts_for_its_scaffold(hinge) -> None:
    expected = hinge.arm_helices * hinge.total_length - hinge.scaffold.deletions
    assert hinge.scaffold.routed_nt == expected
    assert hinge.scaffold.unused_nt == hinge.scaffold.total_nt - expected


def test_the_joint_is_left_unpaired(hinge) -> None:
    """This is what makes it a hinge. A staple spanning the joint would splint
    it into a single rigid plate, and nothing else in the design would say so.
    """
    joint = range(hinge.arm_length, hinge.arm_length + hinge.joint_nt)
    for staple in ad.staples(hinge.design):
        for domain in staple.domains:
            if isinstance(domain, sc.Domain):
                covered = range(domain.start, domain.end)
                assert not (set(covered) & set(joint)), (
                    f"a staple covers joint offsets {sorted(set(covered) & set(joint))}"
                )


def test_there_are_exactly_two_latch_extensions_and_they_are_complementary(hinge) -> None:
    extensions = [
        (s, d) for s in ad.staples(hinge.design) for d in s.domains if isinstance(d, sc.Extension)
    ]
    assert len(extensions) == 2
    sequences = sorted(d.dna_sequence for _, d in extensions)
    assert sequences == sorted([DEFAULT_LATCH, reverse_complement(DEFAULT_LATCH)])


def test_the_latch_sequences_are_actually_assigned(hinge) -> None:
    """An unassigned extension reads as '?' and would be ordered as one. The
    scaffold cannot reach an extension, so this is not automatic."""
    for staple in ad.staples(hinge.design):
        for domain in staple.domains:
            if isinstance(domain, sc.Extension):
                assert domain.dna_sequence
                assert "?" not in domain.dna_sequence


def test_the_two_latch_halves_sit_on_opposite_arms(hinge) -> None:
    arms = set()
    for staple in ad.staples(hinge.design):
        if not any(isinstance(d, sc.Extension) for d in staple.domains):
            continue
        bound = [d for d in staple.domains if isinstance(d, sc.Domain)]
        arms.add("a" if max(d.end for d in bound) <= hinge.arm_length else "b")
        if arms == {"a", "b"}:
            break
    assert arms == {"a", "b"}


def test_the_design_has_no_rule_violations(hinge) -> None:
    """Warnings are expected and match the rectangle's profile; a violation is
    not. The rectangle's first version had twelve, found here and not by
    reasoning ahead."""
    report = lint(hinge.design)
    violations = [v for v in report.violations if v.severity is Severity.VIOLATION]
    assert violations == []


def test_the_predicted_field_is_the_latch_thermodynamics(hinge) -> None:
    assert hinge.field_kt() == pytest.approx(latch_field_kt(duplex(DEFAULT_LATCH)))


def test_the_conformational_offset_is_reported_as_unmeasured(hinge) -> None:
    assert "not predicted" in hinge.as_dict()["conformational_offset"]


def test_an_arm_that_does_not_tile_is_refused() -> None:
    with pytest.raises(ValueError, match=f"multiple of {SPAN_MULTIPLE_NT}"):
        bistable_hinge(arm_length=160)


def test_a_self_complementary_latch_is_refused() -> None:
    with pytest.raises(ValueError, match="self-complementary"):
        bistable_hinge(latch_sequence="GCGCGCGC")


def test_a_latch_helix_with_no_pair_staple_is_refused_not_moved() -> None:
    """Block parity alternates along an arm, so helix 0 is paired at one end
    and takes an edge staple at the other. Silently sliding the latch to a
    neighbouring helix would change the mechanism without saying so."""
    assert pair_lower(0, block_index=1, helices=12) is None
    with pytest.raises(ValueError, match="edge staple"):
        bistable_hinge(latch_helix=0)


def test_a_joint_needs_at_least_one_base() -> None:
    with pytest.raises(ValueError, match="unpaired base"):
        bistable_hinge(joint_nt=0)


def test_a_design_too_big_for_its_scaffold_is_refused() -> None:
    with pytest.raises(ValueError, match="nt of scaffold"):
        bistable_hinge(arm_helices=24, arm_length=640)


@pytest.mark.parametrize("joint", [4, 8, 16, 32])
def test_the_joint_length_is_a_free_knob(joint: int) -> None:
    h = bistable_hinge(joint_nt=joint)
    assert h.joint_nt == joint
    assert h.total_length == 2 * h.arm_length + joint

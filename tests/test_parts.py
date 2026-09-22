"""The parts are pinned by their accounting, not by a golden file.

Q1's acceptance criteria are specific: the designs must open in scadnano and
export to cadnano v2, the scaffold accounting must be exact, and staple counts
and lengths must be pinned. Each of those is a test here.

The mass-balance test is the one that would catch a subtly wrong router: if
every scaffold base is paired exactly once, the staples must sum to the same
total. A tiling bug that overlaps or skips bases breaks that equality long
before it looks wrong in a picture.
"""

from __future__ import annotations

import itertools

import pytest

from dobladillo import _scadnano as ad
from dobladillo.constants import SCAFFOLD_LENGTHS_NT, SQUARE_TWIST_CORRECTION_PERIOD_BP
from dobladillo.parts.bundle import HELICES, RING_POSITIONS, six_helix_bundle
from dobladillo.parts.rectangle import rothemund_rectangle


@pytest.fixture(scope="module")
def rectangle():
    return rothemund_rectangle()


@pytest.fixture(scope="module")
def bundle():
    return six_helix_bundle()


# ------------------------------------------------------------------ rectangle


def test_rectangle_scaffold_accounting_is_exact(rectangle) -> None:
    raw = rectangle.helices * rectangle.length
    assert rectangle.scaffold.routed_nt == raw - rectangle.scaffold.deletions
    assert rectangle.scaffold.routed_nt + rectangle.scaffold.unused_nt == (
        rectangle.scaffold.total_nt
    )


def test_rectangle_every_scaffold_base_is_paired_exactly_once(rectangle) -> None:
    scaffold_nt = ad.scaffold_strand(rectangle.design).dna_length()
    staple_nt = sum(s.dna_length() for s in ad.staples(rectangle.design))
    assert staple_nt == scaffold_nt


def test_rectangle_staple_count_and_lengths_are_pinned(rectangle) -> None:
    assert rectangle.staple_count == 220
    assert set(rectangle.staple_lengths) == {30, 32}


def test_rectangle_staples_obey_the_length_rule(rectangle) -> None:
    from dobladillo.constants import STAPLE_LENGTH_NT

    low, high = STAPLE_LENGTH_NT
    assert all(low <= n <= high for n in rectangle.staple_lengths)


def test_rectangle_twist_correction_is_evenly_spaced_and_off_the_crossovers(rectangle) -> None:
    """Check what the deletions are FOR, not how many the loop happened to emit.

    Two properties matter: they must sit exactly one correction period apart,
    because that spacing is what cancels the lattice's overwinding, and none
    may land on a crossover position, where a deletion is needless strain on a
    junction. Counting them instead would only restate the loop bounds.
    """
    from dobladillo.parts.rectangle import DOMAIN_NT

    scaffold = ad.scaffold_strand(rectangle.design)
    per_helix = {d.helix: sorted(d.deletions) for d in scaffold.domains}
    assert len(per_helix) == rectangle.helices

    for offsets in per_helix.values():
        assert offsets, "every helix takes its share of the correction"
        gaps = {b - a for a, b in itertools.pairwise(offsets)}
        assert gaps == {SQUARE_TWIST_CORRECTION_PERIOD_BP}
        assert all(o % DOMAIN_NT for o in offsets), "a deletion landed on a crossover"

    total = sum(len(o) for o in per_helix.values())
    assert rectangle.scaffold.deletions == total


def test_rectangle_without_twist_correction_has_no_deletions() -> None:
    plain = rothemund_rectangle(twist_corrected=False)
    assert plain.scaffold.deletions == 0
    assert plain.scaffold.routed_nt == plain.helices * plain.length


def test_rectangle_exports_to_cadnano_v2(rectangle) -> None:
    assert ad.roundtrips_through_cadnano_v2(rectangle.design)


def test_rectangle_rejects_geometry_that_would_not_tile() -> None:
    with pytest.raises(ValueError, match="multiple of"):
        rothemund_rectangle(length=100)
    with pytest.raises(ValueError, match="even"):
        rothemund_rectangle(helices=23)


def test_rectangle_rejects_an_odd_number_of_blocks() -> None:
    """288 tiles as 32-blocks but gives nine of them, and the ninth puts a
    staple crossover exactly on the scaffold's turn. Caught by the rule
    checker, so the generator refuses it rather than emitting it again."""
    with pytest.raises(ValueError, match="odd number of blocks"):
        rothemund_rectangle(length=288)


def test_rectangle_refuses_to_outrun_the_scaffold() -> None:
    with pytest.raises(ValueError, match="scaffold"):
        rothemund_rectangle(helices=24, length=384)


# --------------------------------------------------------------------- bundle


def test_ring_is_a_closed_cycle_of_touching_neighbours() -> None:
    """The six positions must form a ring, or it is not a bundle.

    Checked against scadnano's own coordinates rather than a remembered
    honeycomb convention: consecutive positions sit exactly one inter-helix
    spacing apart, and the last closes back onto the first.
    """
    spacing = ad.interhelix_spacing_nm()
    for i in range(HELICES):
        a = RING_POSITIONS[i]
        b = RING_POSITIONS[(i + 1) % HELICES]
        assert ad.neighbour_distance_nm(a, b, grid="honeycomb") == pytest.approx(spacing)


def test_ring_centre_is_hollow() -> None:
    """Opposite helices are two spacings apart, which leaves a hole."""
    spacing = ad.interhelix_spacing_nm()
    for i in range(HELICES // 2):
        across = ad.neighbour_distance_nm(
            RING_POSITIONS[i], RING_POSITIONS[i + HELICES // 2], grid="honeycomb"
        )
        assert across > spacing


def test_bundle_scaffold_accounting_is_exact(bundle) -> None:
    assert bundle.scaffold.routed_nt == HELICES * bundle.length
    assert bundle.scaffold.routed_nt + bundle.scaffold.unused_nt == bundle.scaffold.total_nt


def test_bundle_every_scaffold_base_is_paired_exactly_once(bundle) -> None:
    scaffold_nt = ad.scaffold_strand(bundle.design).dna_length()
    staple_nt = sum(s.dna_length() for s in ad.staples(bundle.design))
    assert staple_nt == scaffold_nt


def test_bundle_staple_count_and_lengths_are_pinned(bundle) -> None:
    """Two staple sizes, not one, and that is the fix rather than a regression.

    Equal spans tile at multiples of 21 and put every crossover at the same
    helical phase, which is what bent the first version into a 269 nm arc.
    Spans of 28 and 14 put the two pair families at different phases, at the
    cost of 56 nt and 28 nt staples instead of a uniform 42. Both are inside
    the hard length limits and outside the preferred band, so the linter warns
    and does not block. See docs/BUNDLE_BEND.md.
    """
    assert bundle.staple_count == 168
    assert set(bundle.staple_lengths) == {28, 56}


def test_bundle_needs_no_twist_correction(bundle) -> None:
    """Honeycomb is twist-neutral. A deletion here would be a bug, not a fix."""
    assert bundle.scaffold.deletions == 0


def test_bundle_exports_to_cadnano_v2(bundle) -> None:
    assert ad.roundtrips_through_cadnano_v2(bundle.design)


# ------------------------------------------------- the library we depend on


def test_scaffold_lengths_match_scadnanos_own() -> None:
    """Our table is a copy; this fails the day it stops being a true one."""
    assert ad.available_scaffolds() == SCAFFOLD_LENGTHS_NT


def test_the_rise_per_base_pair_disagreement_is_still_what_we_documented() -> None:
    """A tripwire, not an assertion that either value is right.

    constants.RISE_PER_BP_NM is the literature figure; scadnano uses its own.
    They differ by 2.4%, which lands in every predicted dimension, so the gap
    is pinned: if scadnano changes its value, this fails and someone re-reads
    the note instead of inheriting a silent shift.
    """
    from dobladillo.constants import RISE_PER_BP_NM

    assert ad.GEOMETRY.rise_per_base_pair == pytest.approx(0.332)
    relative = abs(RISE_PER_BP_NM - ad.GEOMETRY.rise_per_base_pair)
    assert relative == pytest.approx(0.008, abs=1e-6)

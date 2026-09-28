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
    # 32 nt, less one or two twist-correcting deletions.
    assert set(rectangle.staple_lengths) == {30, 31, 32}


def test_rectangle_is_phased_like_published_designs(rectangle) -> None:
    """The defect that blocked E1: half the crossovers on the wrong face.

    Measured the same way as the published references in
    tests/data/reference_designs, which score 18-22 deg; the old tiling scored
    89 deg with 47% of its crossovers on the wrong face.
    """
    from dobladillo.routing.azimuth import measure

    report = measure(rectangle.design)
    assert report.rms_deg < 25
    assert not report.wrong_face
    assert not report.carries_twist


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
    from dobladillo.parts.rectangle import COLUMN_NT

    # A helix can carry more than one scaffold domain (the seam splits them).
    per_helix: dict[int, list[int]] = {}
    for d in ad.scaffold_strand(rectangle.design).domains:
        per_helix.setdefault(d.helix, []).extend(d.deletions)
    per_helix = {h: sorted(o) for h, o in per_helix.items()}
    assert len(per_helix) == rectangle.helices

    for offsets in per_helix.values():
        assert offsets, "every helix takes its share of the correction"
        gaps = {b - a for a, b in itertools.pairwise(offsets)}
        assert gaps == {SQUARE_TWIST_CORRECTION_PERIOD_BP}
        assert all(o % COLUMN_NT for o in offsets), "a deletion landed on a crossover"

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


def test_rectangle_rejects_a_partial_correction_period() -> None:
    """288 is 4.5 periods of the twist correction; the last half would be
    left uncorrected."""
    with pytest.raises(ValueError, match="partial period"):
        rothemund_rectangle(length=288)


def test_rectangle_refuses_a_size_scadnano_cannot_tile() -> None:
    """Found by accident: 64 bp is four columns, and scadnano's generator
    draws an edge staple past the helix end. Refused with a reason, not a
    StrandError from inside the library."""
    with pytest.raises(ValueError, match="at least 128"):
        rothemund_rectangle(helices=4, length=64)


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
    from dobladillo.parts.bundle import END_NT

    assert bundle.scaffold.routed_nt == HELICES * (bundle.length + 2 * END_NT)
    assert bundle.scaffold.routed_nt + bundle.scaffold.unused_nt == bundle.scaffold.total_nt


def test_bundle_pairs_every_scaffold_base_but_the_turning_ends(bundle) -> None:
    """Every base is paired exactly once, except END_NT at each helix end,
    left single-stranded on purpose so the scaffold turns without a phase."""
    from dobladillo.parts.bundle import END_NT

    scaffold_nt = ad.scaffold_strand(bundle.design).dna_length()
    staple_nt = sum(s.dna_length() for s in ad.staples(bundle.design))
    assert staple_nt == scaffold_nt - 2 * END_NT * HELICES


def test_bundle_staple_count_and_lengths_are_pinned(bundle) -> None:
    """168 staples of 42 nt: scaffold's published unit, four blocks of six
    staples per 168 bp. The 28/14 split that came before it made 56 and 28 nt
    staples and was still misphased; see parts/bundle.py."""
    assert bundle.staple_count == 168
    assert set(bundle.staple_lengths) == {42}


def test_bundle_is_phased_like_published_designs(bundle) -> None:
    from dobladillo.routing.azimuth import measure

    report = measure(bundle.design)
    assert report.rms_deg < 22
    assert not report.wrong_face
    # The scaffold's six end turns, in single-stranded DNA by design -- and
    # no others: a staple crossover there would be a tiling bug.
    assert report.unconstrained == 2 * (HELICES - 1)


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

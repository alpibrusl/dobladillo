"""E9's part: two rectangles that join end to end.

What is worth pinning here, in the order it could go wrong:

- A and B are E1's rectangle everywhere except the edge staples. If that
  fails, the order is 440 oligos rather than 44, and -- worse -- the footprint
  E1 measured is no longer the footprint E9 predicts.
- every helix end on every edge carries something: a sticky end, or a 4-T
  tail. A blunt one polymerises (Rothemund 2006 S5.7).
- the interface is declared, so `interfaces.crosstalk` checks it, and it
  fails when the channel is mis-assigned. A check that cannot fail is not one.
- the sticky ends meet the four thermodynamic conditions, and the pinned
  sequences are what the search returns.
"""

from __future__ import annotations

import pytest
import scadnano as sc

from dobladillo import _scadnano as ad
from dobladillo.interfaces import Bond, Brick, Port, crosstalk, unsatisfied
from dobladillo.parts.dimer import (
    DEFAULT_CONDITIONS,
    EDGE_STAPLES,
    POLY_T,
    SPACER,
    STICKY_ENDS,
    Conditions,
    check_sticky_ends,
    design_sticky_ends,
    extension,
    rectangle_dimer,
    search_inputs,
    single_stranded_scaffold,
)
from dobladillo.parts.rectangle import COLUMN_NT, rothemund_rectangle
from dobladillo.sequence.thermo import reverse_complement


@pytest.fixture(scope="module")
def dimer():
    return rectangle_dimer()


@pytest.fixture(scope="module")
def e1_staples() -> set[str]:
    return {s.dna_sequence for s in ad.staples(rothemund_rectangle().design)}


# --------------------------------------------------------------- shared pool


def test_a_and_b_share_every_staple_but_the_edge_carriers(dimer, e1_staples) -> None:
    """The LegoGen lesson, as `tests/test_hinge.py` pins it for the latch
    ladder: variants that differ in a few strands share the rest, so E9 orders
    the difference. 22 of 220 differ -- 11 sticky, 11 passivated -- and the
    other 198 are E1's, byte for byte."""
    for component in (dimer.a, dimer.b):
        theirs = component.staple_sequences
        assert len(theirs) == len(e1_staples) == 220
        assert len(theirs - e1_staples) == 2 * EDGE_STAPLES
        assert len(theirs & e1_staples) == 220 - 2 * EDGE_STAPLES
    # And the two components share that same core with each other.
    shared = dimer.a.staple_sequences & dimer.b.staple_sequences
    assert len(shared) == 220 - 2 * EDGE_STAPLES
    assert shared <= e1_staples


def test_every_changed_staple_is_an_e1_staple_plus_extensions(dimer, e1_staples) -> None:
    """A modified staple keeps E1's bound sequence exactly: the core is what
    pairs with the scaffold, and a change there would be a different design
    wearing E1's footprint."""
    for component in (dimer.a, dimer.b):
        for staple in component.extra:
            assert staple.core in e1_staples
            assert staple.sequence == staple.five_prime + staple.core + staple.three_prime
            assert staple.sequence not in e1_staples


def test_the_extra_staples_are_the_only_ones_the_base_plates_lack(dimer) -> None:
    """What `lab order dimer` promises: pool 198 wells from E1's plates, order
    22 per component. Checked against the plate layout E1 was ordered from."""
    from dobladillo.lab.dimer import pool_plan

    pool, layout = pool_plan(dimer)
    assert pool.base_wells == 220
    assert len(pool.core) == 220 - 2 * EDGE_STAPLES
    for name, component in (("A", dimer.a), ("B", dimer.b)):
        variant = pool.variant(name)
        assert sorted(variant.extra) == sorted(s.sequence for s in component.extra)
        assert len(variant.skip) == 2 * EDGE_STAPLES
        assert len(variant.from_base) == 220 - 2 * EDGE_STAPLES
    # Every skipped well holds an edge staple, which is the well a variant
    # replaces. Pooling it anyway is the failure `POOL_WARNING` is about.
    skipped = {w.sequence for w in pool.variant("A").skip}
    assert skipped == {s.core for s in dimer.a.extra}


def test_the_committed_e1_plates_are_the_plates_this_pools_from(dimer) -> None:
    """The pooling instructions name plate and well. If E1's committed
    workbook put those staples elsewhere, a student would pool the wrong tube
    -- so the layout is checked against the file, not against itself."""
    import openpyxl

    from dobladillo.lab.dimer import pool_plan

    path = "experiments/2026-09-22-rectangle-afm/pre/order/rectangle_plates.xlsx"
    workbook = openpyxl.load_workbook(path)
    committed = {
        (sheet, row[0]): (row[1], row[2])
        for sheet in workbook.sheetnames
        for row in workbook[sheet].iter_rows(min_row=2, values_only=True)
        if row[0]
    }
    _, layout = pool_plan(dimer)
    assert len(committed) == len(layout.wells)
    for well in layout.wells:
        assert committed[(well.plate, well.well)] == (well.name, well.sequence)


# ------------------------------------------------------------------- edges


def _edge_ends(design: sc.Design, length: int) -> dict[str, list[tuple[int, str]]]:
    """Every staple end sitting on an edge, and what follows or precedes it."""
    ends: dict[str, list[tuple[int, str]]] = {"start": [], "end": []}
    for strand in ad.staples(design):
        bound = [d for d in strand.domains if isinstance(d, sc.Domain)]
        five, three = bound[0], bound[-1]
        five_offset = five.start if five.forward else five.end - 1
        three_offset = three.end - 1 if three.forward else three.start
        for offset, helix, index in (
            (five_offset, five.helix, 0),
            (three_offset, three.helix, -1),
        ):
            edge = "start" if offset == 0 else "end" if offset == length - 1 else None
            if edge is None:
                continue
            first_or_last = strand.domains[index]
            carried = (
                first_or_last.dna_sequence or "" if isinstance(first_or_last, sc.Extension) else ""
            )
            ends[edge].append((helix, carried))
    return ends


def test_no_helix_end_on_any_edge_is_left_blunt(dimer) -> None:
    """Rothemund 2006 S5.7: blunt ends along an edge stack into chains over
    5 um long. Every one of the 22 helix ends on each edge must carry a tail
    or a sticky end."""
    for component in (dimer.a, dimer.b):
        ends = _edge_ends(component.design, component.length)
        for edge in ("start", "end"):
            assert len(ends[edge]) == 2 * EDGE_STAPLES
            assert {helix for helix, _ in ends[edge]} == set(range(component.helices))
            assert all(carried for _, carried in ends[edge]), (component.name, edge)


def test_the_mating_edge_carries_the_sticky_ends_and_the_other_does_not(dimer) -> None:
    for component, sticky in (
        (dimer.a, STICKY_ENDS),
        (dimer.b, tuple(map(reverse_complement, STICKY_ENDS))),
    ):
        ends = _edge_ends(component.design, component.length)
        mating = {carried for _, carried in ends[component.mating_edge]}
        outer = {carried for _, carried in ends[component.outer_edge]}
        assert mating == {POLY_T, *(extension(s) for s in sticky)}
        assert outer == {POLY_T}


def test_a_sticky_end_joins_one_helix_of_a_to_one_of_b(dimer) -> None:
    """Sticky end k hangs from A's helix 2k+1 and B's helix 2k, so the eleven
    bonds are spread along the whole 66 nm edge rather than bunched."""
    a = {s.pair: s.helix_3p for s in dimer.a.extra if s.role == "sticky"}
    b = {s.pair: s.helix_3p for s in dimer.b.extra if s.role == "sticky"}
    assert sorted(a) == sorted(b) == list(range(EDGE_STAPLES))
    assert [a[k] for k in sorted(a)] == [2 * k + 1 for k in range(EDGE_STAPLES)]
    assert [b[k] for k in sorted(b)] == [2 * k for k in range(EDGE_STAPLES)]


def test_omitting_the_outer_edge_staples_is_the_alternative_and_costs_a_column() -> None:
    """Rothemund's other cure. Offered, not chosen: it leaves single-stranded
    scaffold along the outer edge and shortens the monomer by one column, so A
    and B would no longer have E1's measured footprint."""
    omitted = rectangle_dimer(outer="omit")
    assert all(len(c.omitted) == EDGE_STAPLES for c in (omitted.a, omitted.b))
    assert len(omitted.a.staple_sequences) == 220 - EDGE_STAPLES
    assert omitted.monomer_nm[0] < rectangle_dimer().monomer_nm[0]
    # And the bare edge is now single-stranded scaffold the checks must see.
    bare = single_stranded_scaffold(omitted.a.design, variant="p7249", rotation=5587)
    assert sum(len(s) for s in bare) > sum(
        len(s) for s in single_stranded_scaffold(dimer_design(), variant="p7249", rotation=5587)
    )


def dimer_design():
    return rectangle_dimer().a.design


def test_blunt_edges_are_available_as_the_stacking_control(dimer, e1_staples) -> None:
    """`outer="blunt"` keeps E1's plain edge staples: the control that should
    polymerise. Its outer edge staples are E1's, unchanged."""
    blunt = rectangle_dimer(outer="blunt")
    assert len(blunt.a.staple_sequences - e1_staples) == EDGE_STAPLES
    ends = _edge_ends(blunt.a.design, blunt.a.length)
    assert {carried for _, carried in ends[blunt.a.outer_edge]} == {""}


def test_the_scaffold_is_fully_accounted_for(dimer) -> None:
    """The routing is E1's, so the accounting must be too: nothing is lost by
    replacing strands and re-assigning the sequence."""
    for component in (dimer.a, dimer.b):
        assert component.scaffold.routed_nt == dimer.base.scaffold.routed_nt
        assert component.scaffold.unused_nt == dimer.base.scaffold.unused_nt
        assert component.scaffold.deletions == dimer.base.scaffold.deletions


def test_the_single_stranded_scaffold_is_the_unrouted_loop(dimer) -> None:
    """With every edge staple present, the only unpaired scaffold is the loop
    -- and it is the loop's own sequence, not a placeholder."""
    runs = single_stranded_scaffold(dimer.a.design, variant="p7249", rotation=5587)
    assert len(runs) == 1
    assert len(runs[0]) == dimer.base.scaffold.unused_nt == 319
    assert set(runs[0]) <= set("ACGT")


# --------------------------------------------------------------- interface


def test_the_mating_ports_are_declared_and_mate(dimer) -> None:
    bricks = dimer.bricks()
    assert [p.name for p in bricks["A"].ports] == ["end"]
    assert [p.name for p in bricks["B"].ports] == ["start"]
    assert dimer.interface_problems() == {"crosstalk": [], "unsatisfied": []}
    assert not crosstalk(bricks, (dimer.bond,))
    assert not unsatisfied(bricks, (dimer.bond,))


def test_a_mis_assigned_channel_breaks_the_bond_and_the_check_says_so(dimer) -> None:
    """The negative control for the check above. Two ports mate only within a
    channel, so putting B's edge on another one leaves the intended bond
    unsatisfied -- and a check that could not fail would be worth nothing."""
    bricks = dimer.bricks(channel_b=dimer.channel + 1)
    problems = unsatisfied(bricks, (dimer.bond,))
    assert problems and "do not mate" in problems[0]
    assert "different signatures" in problems[0]


def test_a_third_rectangle_on_the_same_channel_is_crosstalk(dimer) -> None:
    """Why the pair is declared at all. Add a plain rectangle with both edges
    on E9's channel and there are now two ways to make one interface, which
    no sequence design fixes."""
    bricks = dimer.bricks()
    bricks["C"] = dimer.base.brick(channel=dimer.channel)
    found = crosstalk(bricks, (dimer.bond,))
    assert found
    assert {(c.left, c.right) for c in found} == {("A", "C"), ("B", "C")}


def test_ports_of_different_widths_cannot_mate(dimer) -> None:
    """A port's width is its helix count; a narrower edge is a different
    interface even on the same channel."""
    narrow = Brick(
        name="narrow",
        ports=(
            Port(
                name="start",
                kind="edge",
                polarity="a",
                helices=(0, 1),
                offset=0,
                channel=dimer.channel,
            ),
        ),
    )
    bond = Bond(left="A", left_port="end", right="N", right_port="start")
    assert unsatisfied({"A": dimer.bricks()["A"], "N": narrow}, (bond,))


# ----------------------------------------------------------- thermodynamics


def test_the_pinned_sticky_ends_pass_every_condition(dimer) -> None:
    report = dimer.report()
    assert report.passed, report.failures
    assert len(report.findings) == 5
    assert all(f.checked > 0 for f in report.findings)
    # The conditions are separated so a failure says which one: the intended
    # bond has a floor, everything else a ceiling.
    intended, *unintended = report.findings
    assert intended.worst is not None
    assert intended.worst.melting_c >= DEFAULT_CONDITIONS.intended_min_tm_c
    for finding in unintended:
        assert finding.worst is None or finding.worst.melting_c < finding.limit_c


def test_the_intended_bonds_melt_above_the_mixing_temperature(dimer) -> None:
    """Every one of the eleven, not just the weakest: a bond that melts below
    the mix is a contact that rarely forms, and the joint needs them all."""
    for h in dimer.report().intended:
        assert h.found
        assert h.melting_c > DEFAULT_CONDITIONS.mixing_temperature_c


def test_the_search_reproduces_the_pinned_sequences() -> None:
    """The sequences in `STICKY_ENDS` are the search's output, so they can be
    regenerated -- and so a change to the conditions cannot silently leave
    them behind. `candidate` hashes a counter rather than drawing from an RNG
    for exactly this reason."""
    staples, single = search_inputs()
    assert design_sticky_ends(staples=staples, single_strands=single) == STICKY_ENDS


def test_ten_nucleotides_is_too_short_to_find_eleven_orthogonal_ends() -> None:
    """Why 12 and not less. This is the measurement the module's choice rests
    on, so it is re-run rather than asserted in a comment. A short candidate
    budget: the point is that it fails, and at 10 nt it fails immediately."""
    staples, single = search_inputs()
    with pytest.raises(ValueError, match="longer sticky end"):
        design_sticky_ends(length=10, staples=staples, single_strands=single, max_candidates=400)


def test_a_five_nucleotide_sticky_end_melts_far_below_the_mix() -> None:
    """The DNA-only control of Zou et al. 2023 used 5-nt sticky ends and got
    7-23% dimers. This is why: at the mixing concentration such a bond is
    open almost all the time."""
    report = check_sticky_ends(("GCTAC",), staples=(), single_strands=())
    assert not report.passed
    assert "intended bond" in report.failures[0]
    weakest = report.findings[0].worst
    assert weakest is not None
    assert weakest.melting_c < 0.0


def test_a_self_complementary_sticky_end_is_refused() -> None:
    """It would bind its own copies as readily as its partner, which is a
    homodimer by construction."""
    palindrome = "AACACATGTGTT"
    assert reverse_complement(palindrome) == palindrome
    with pytest.raises(ValueError, match="self-complementary"):
        check_sticky_ends((palindrome,), staples=(), single_strands=())


def test_a_sticky_end_that_matches_a_staple_is_caught() -> None:
    """The condition that needs the whole design, not just the sticky set: a
    sticky end complementary to a staple is captured by the staple excess the
    sample sits in until purification."""
    staples, single = search_inputs()
    victim = next(s for s in staples if len(s) >= 12)
    parasite = reverse_complement(victim[:12])
    report = check_sticky_ends((parasite,), staples=staples, single_strands=single)
    assert not report.passed
    assert any("staple cross-binding" in f for f in report.failures)


def test_a_sticky_end_that_matches_the_scaffold_loop_is_caught() -> None:
    """Every monomer carries 319 nt of unpaired scaffold. A sticky end that
    finds it cross-links two monomers, and no purification removes that."""
    staples, single = search_inputs()
    loop = single[0]
    parasite = reverse_complement(loop[40:52])
    report = check_sticky_ends((parasite,), staples=(), single_strands=single)
    assert not report.passed
    assert any("scaffold cross-binding" in f for f in report.failures)


def test_two_sticky_ends_that_are_each_others_complement_are_refused() -> None:
    """Both halves of one bond on A's edge: A self-dimerises. Refused rather
    than reported, because the pairwise check cannot see it -- that pair of
    strands is also an INTENDED pair, so it is skipped. Found by this test
    while the check passed it."""
    first = STICKY_ENDS[0]
    with pytest.raises(ValueError, match="the same bond"):
        check_sticky_ends((first, reverse_complement(first)), staples=(), single_strands=())
    with pytest.raises(ValueError, match="the same bond"):
        check_sticky_ends((first, first), staples=(), single_strands=())


def test_a_mis_registered_pair_of_sticky_ends_is_reported() -> None:
    """The case the pairwise check IS for: two different bonds whose halves
    cross-bind, so A's sticky end k finds B's partner for j."""
    first = STICKY_ENDS[0]
    almost = reverse_complement(first)[:-1] + ("A" if first[0] != "T" else "C")
    report = check_sticky_ends((first, almost), staples=(), single_strands=())
    assert not report.passed
    assert any("unintended pairing" in f for f in report.failures)


def test_the_spacer_is_part_of_every_extension(dimer) -> None:
    """Two bases between the staple's 3' end and the sticky sequence, so the
    bridging duplex does not have to shear two adjacent helix ends."""
    for staple in dimer.a.extra:
        if staple.role == "sticky":
            assert staple.three_prime.startswith(SPACER)
            assert len(staple.three_prime) == len(SPACER) + len(STICKY_ENDS[0])


def test_the_salt_correction_is_the_buffer_minus_the_edta() -> None:
    """EDTA binds magnesium one to one, so the free magnesium is the nominal
    value minus 1 mM (common-techniques s1). Designing at the nominal value
    would overstate every Tm."""
    conditions = Conditions()
    assert conditions.magnesium_free_m == pytest.approx(0.011)
    warmer = check_sticky_ends(
        STICKY_ENDS[:1],
        staples=(),
        single_strands=(),
        conditions=Conditions(magnesium_nominal_mm=24.0),
    )
    cooler = check_sticky_ends(STICKY_ENDS[:1], staples=(), single_strands=())
    assert warmer.findings[0].worst.melting_c > cooler.findings[0].worst.melting_c


# ------------------------------------------------------------------ shapes


def test_the_dimer_is_twice_as_long_and_no_wider(dimer) -> None:
    length, width = dimer.monomer_nm
    assert dimer.dimer_length_nm == pytest.approx(2 * length + dimer.gap_nm)
    assert dimer.gap_nm < 0.05 * dimer.dimer_length_nm
    assert dimer.as_dict(with_report=False)["approx_dimensions_nm"]["monomer_width"] == round(
        width, 1
    )


def test_the_monomer_is_e1s_rectangle_to_the_nanometre(dimer) -> None:
    """E9's monomer prediction has to be E1's measured footprint, or E1's
    result says nothing about it."""
    assert dimer.monomer_nm == rothemund_rectangle().dimensions_nm


def test_an_edge_staple_spans_exactly_one_column(dimer) -> None:
    """What `_edge_staples` assumes about scadnano's layout, asserted: a 3'
    extension on a staple that reached into the sheet would hang in the wrong
    place, and scadnano's generator is not ours."""
    for strand in ad.staples(dimer.base.design):
        bound = [d for d in strand.domains if isinstance(d, sc.Domain)]
        if max(d.end for d in bound) <= COLUMN_NT:
            assert {(d.end - d.start) for d in bound} == {COLUMN_NT}
            assert len(bound) == 2


def test_the_design_hash_covers_both_components(dimer) -> None:
    """The assembly is one node of the provenance chain, and it changes when
    either component does."""
    from dobladillo import provenance

    assert dimer.design_hash() != provenance.design_sha256(dimer.a.design)
    other = rectangle_dimer(sticky=(*STICKY_ENDS[:-1], "AGACTTAACACA"))
    assert other.design_hash() != dimer.design_hash()


def test_the_components_export_and_round_trip(dimer) -> None:
    """caDNAno v2 cannot express extensions, and that is a real limit rather
    than a bug here: the .sc and oxDNA paths must still work, because the
    simulation and the viewer are what a reviewer looks at."""
    assert ad.roundtrips_through_cadnano_v2(dimer.base.design)
    with pytest.raises(ValueError):
        ad.cadnano_v2_text(dimer.a.design, name="A")


def test_every_extension_is_a_particle_oxdna_will_see(dimer) -> None:
    """The bug this repeats a guard for: the hinge's two latches made the
    nucleotide map 16 short of the topology, so a traps file restrained the
    wrong particles. Here there are 44 extensions per component."""
    for component in (dimer.a, dimer.b):
        indices = ad.nucleotide_indices(component.design)
        extensions = ad.extension_indices(component.design)
        assert len(extensions) == 2 * 2 * EDGE_STAPLES
        flat = [i for _, ids in extensions for i in ids]
        assert len(flat) == len(set(flat))
        assert set(flat).isdisjoint(indices.values())
        assert len(indices) + len(flat) == sum(s.dna_length() for s in component.design.strands)

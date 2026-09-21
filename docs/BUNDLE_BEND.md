# Why the six-helix bundle bends

An oxDNA production run gave the bundle as **328.2 ± 3.2 × 70.1 ± 4.0 ×
17.7 ± 1.8 nm** against a design of 390.4 × 8.0, with 51.5 nm of axis bend. A
six-helix bundle has a persistence length in the microns; a 390 nm one should
be nearly straight. This is what it turned out to be.

## It is not under-relaxation

The bend is **stationary** across the 200-frame production run — quintile means
of 52.8, 54.4, 49.9, 48.7, 50.9 nm, and a linear drift of −4.4 nm, which is
1.6 sd. The structure is equilibrated in this degree of freedom.

## It is not thermal

The give-away is the **spread**, not the mean: bend is 51 nm with a standard
deviation of **2.7 nm**. Five per cent. A thermal bending mode has a Boltzmann
amplitude and fluctuates on the order of its own size.

The decisive test is direction. Intrinsic curvature points the same way in the
molecule's own frame; thermal bending wanders. Expressing the bend direction in
the body frame each frame and taking the orientational order parameter:

| | |
|---|---|
| order parameter | **0.993** (1 = always the same way, 0 = random) |
| radius of curvature | 269 ± 11 nm |
| relative spread | 3.9% |

The bundle is not bending. It is **curved**, by design, and always the same way.

## The cause: every crossover is at the same helical phase

A crossover can only form where the backbone faces the neighbour helix, so the
offset at which one happens *is* an angle. The backbone advances 34.29° per
base pair, so honeycomb's 7 bp crossover spacing is 240° — the same as −120°,
which is exactly the angular separation of neighbours on a honeycomb lattice.
That is *why* the spacing is 7.

Extracting the crossovers of the built design, by pair:

| pair | offsets | phase (mod 21) |
|---|---|---|
| 0–1 | 0, 21, 84, 105, … | 0 |
| 0–5 | 42, 63, 126, 147, … | 0 |
| 1–2 | 42, 63, … | 0 |
| 2–3 | 0, 21, … | 0 |
| 3–4 | 42, 63, … | 0 |
| 4–5 | 0, 21, … | 0 |

**Every crossover in the object sits at phase 0.** Offsets differing by a whole
period differ by no angle at all, so each helix bonds *both* of its neighbours
at the same backbone azimuth — while those neighbours sit 120° apart
(confirmed: all six separations are 120°, and the cross-section is a perfect
regular hexagon, sides 3.0 nm, long diagonals 6.0).

So one bond of every pair is made 120° off-azimuth. A systematic azimuthal
strain applied the same way around a ring is a constant bend, and that is the
269 nm arc.

## What has changed

A new rule, **`crossover_phase`**, flags a helix that bonds two different
neighbours at an identical set of phases. It fires on the bundle and passes the
rectangle and the hinge.

It is deliberately narrow, and the narrowness is declared. It does not verify
that *each* bond is made at the azimuth its own neighbour direction requires —
that needs the angle between neighbour directions per lattice and is listed in
`UNIMPLEMENTED` as `crossover_azimuth`. The rectangle's phases overlap
partially rather than coinciding, so it passes this rule without having been
cleared by the full one.

The bundle's entry in `test_reference_parts_have_no_hard_violations` is now
`xfail(strict=True)` rather than removed, so it flips to a failure the moment
the routing is fixed.

## What has not

**The routing is not fixed.** The bundle still bends. Fixing it means offsetting
the crossover sets of alternate pairs by 7 bp, which changes the scaffold path,
the staple boundaries and every pinned count in the tests — a deliberate piece
of work rather than a patch, and it should be done with the rule in place to
verify it.

Until then the bundle is a known-curved strut. Nothing in the roadmap's seven
experiments depends on it: E1 and E2 are rectangles, E3–E6 are hinges, E7 is
plates.

## What this cost, and what it bought

The bundle has been in the repository since Q1. It passed six design rules, a
cadnano round trip, exact scaffold accounting and pinned staple counts. None of
those look at helical phase.

It took a production simulation, and then the question *why*, to find it. That
is the closed loop doing the job it exists for — and the reason the fix is a
**rule** rather than an edit to one part.

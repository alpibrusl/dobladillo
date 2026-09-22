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

## The fix: unequal spans

The obvious repair — shift one pair family by 7 bp — does not work, and the
reason is worth writing down. A staple here covers the *same span* on both
helices, so its crossover sits at the span boundary. Spans of equal length tile
at multiples of 21 whatever offset they start from, so the boundaries, and
therefore every crossover, stay at one phase. Shifting a family by 7 leaves a
7 bp gap on one side and a 7 bp overlap on the other.

What works is making the spans **different lengths**. Family A takes 28 bases,
family B takes 14:

| | boundary | phase |
|---|---:|---:|
| A: pairs (0,1), (2,3), (4,5) | 0 → 28 | 28 mod 21 = **7** |
| B: pairs (1,2), (3,4), (5,0) | 28 → 42 | 42 mod 21 = **0** |

Six is even, so every helix belongs to exactly one pair of each family, is
covered once end to end, and bonds its two neighbours at phases 7 apart —
which is what the lattice asks for. Both spans are multiples of the crossover
spacing, so every crossover still lands where one is allowed.

Measured on the rebuilt design, each helix's two neighbours now sit at
different phase sets, and `lint` reports **zero hard violations**.

### What it costs

Staples are 56 nt and 28 nt instead of a uniform 42. Both are inside the hard
limits (20–60) and outside the preferred band, so the linter warns rather than
blocking. That is the trade: uniform staple length was never a design goal, and
correct crossover phasing is.

Scaffold routing, helix count and length are unchanged; 168 staples, 7056 of
M13's 7249 bases, as before.

## Still open

**Whether the fix removes the arc has not been measured yet.** A production run
on the rebuilt design is queued with the same recipe as the one that found the
defect — same relaxation, same million production steps, same sampling — so the
routing is the only thing that differs between them. Until it lands, the fix is
verified against the rule that describes the defect, not against the physics.

The number to beat: **order parameter 0.993, radius 269 ± 11 nm**. A structure
that is merely bending thermally should show a low order parameter and a radius
that fluctuates on the order of itself.

## What this cost, and what it bought

The bundle has been in the repository since Q1. It passed six design rules, a
cadnano round trip, exact scaffold accounting and pinned staple counts. None of
those look at helical phase.

It took a production simulation, and then the question *why*, to find it. That
is the closed loop doing the job it exists for — and the reason the fix is a
**rule** rather than an edit to one part.

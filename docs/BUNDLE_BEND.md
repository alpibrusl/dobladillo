# Why the six-helix bundle bends

> **Update, 2026-09-28: the diagnosis below is refuted.** The rebuilt bundle —
> unequal 28/14 spans, `crossover_phase` clean — was run to 200 production
> frames and came back **exactly as curved**: sagitta 49.9 nm against 50.2,
> 4.94 body widths against 4.7, bend direction fixed in the body frame at
> order parameter 0.995 against 0.993. Fixing the phase *sets* did not move the
> arc. The analysis of why is at the end of this document; the original
> reasoning is kept because the refutation is only readable against it.

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

---

## Refuted: the phase fix did not straighten it

| | original routing | 28/14 spans |
|---|---:|---:|
| sagitta | 50.2 nm | **49.9 nm** |
| body widths | 4.7 | **4.94** |
| order parameter | 0.993 | **0.995** |
| radius of curvature | 269 ± 11 nm | 347 ± 51 nm |

The relaxation differed — 1e6 trapped steps per stage against 1e5, because the
rebuilt design failed production at 1e5 — so the runs are not identical in
every respect. That weakens nothing: a design whose curvature was caused by
bonding both neighbours at one azimuth should have straightened, and it did
not move.

### What this says about the method, which matters more than the bundle

`crossover_phase` checks that two neighbours do not share an **identical set**
of phases. The fix satisfied it. What the fix did not establish is that each
family sits at the *right* phase for its own neighbour direction — the
`crossover_azimuth` check, declared unimplemented from the start. A 14 bp
separation is allowed by the lattice in one handedness and wrong in the
other; the rule cannot tell which.

So the rule was satisfied and the physics was not, which is exactly the gap
the `UNIMPLEMENTED` entry warned about. The mistake was treating a passing
narrow rule as a fix.

### The routing is non-standard in a second way

In every published honeycomb design the **scaffold** crosses between helices
along the length, in a reference frame offset about 5 bp from the staple
crossovers. This bundle's scaffold rasters helix by helix and crosses only at
the ends; the six helices are held together by staples alone. That is a larger
departure from the lattice's intended geometry than the phase sets, and it is
the next hypothesis — untested.

### What should happen instead of another hand-written fix

Stop deriving crossover positions by hand, and stop spending seven-hour
oxDNA runs on shape questions. Under the project's constraint — open source,
self-hosted, no external servers — none of the published fast predictors is
usable: CanDo is a server running commercial Abaqus, SNUPI a non-commercial
binary, NADOC's beam model is unlicensed, mrDNA needs CUDA. So the next step
is to build a small beam finite-element predictor from the published method
(issue #22), validate it against *this* bundle's oxDNA arc, and iterate
routing against it in seconds (issue #5). Then route with the lattice's
canonical crossover positions rather than ours (#6). See `docs/VISION.md`.

---

## Third routing: scadnano's published unit (2026-09-28)

`routing.azimuth`, calibrated on published designs, explained the refutation.
Honeycomb allows each neighbour pair one crossover phase in the 21-bp repeat,
and on the ring that phase is different for each of the SIX pairs: 7, 21 and
35 mod 42 in turn. The 28/14 routing gave each of two *families* one phase,
so two thirds of the crossovers stayed off:

| routing | phasing rms | wrong face |
|---|---:|---:|
| original, 21/21 | 62° | 4 crossovers |
| 28/14 spans | 44° | 1% |
| scadnano's 6HB unit + unpaired scaffold ends | **17°** | 0 |
| published honeycomb designs | 19–22° | 0 |

`parts/bundle.py` now tiles the 42-bp repeating unit of scadnano's example
bundle (MIT). Every staple is 42 nt. The scaffold turns through 5 unpaired
bases at each helix end, because a raster cannot put all six end turns in
phase.

**Physics not yet measured.** An oxDNA run with the same recipe as the two
above (1e6 steps per relaxation stage, 1e6 production steps, 200 frames) was
started on 2026-09-28. This design is straight only if that run's order
parameter falls well below 0.99 and the sagitta well below 50 nm.

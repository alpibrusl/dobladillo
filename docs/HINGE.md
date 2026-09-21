# The bistable hinge, and the measurement window

Epic #2. The first part whose prediction is a distribution rather than a shape.

`dobladillo build hinge` builds it; `dobladillo bracket` prints the ladder below.

## The part

Two arms tiled on the square lattice, joined by unpaired scaffold. One scaffold
rasters the full length of both arms and the joint; staples tile the arms
independently and never span the joint, so the joint's bases are left
single-stranded — one tether per helix, together a flexible line the arms
rotate about. `joint_nt` is a knob, not a constant: shorter stiffens the
mechanism, longer costs conformational entropy on closing, and nothing here can
predict the right value.

The latch is a short duplex between the arms' outer edges, carried as unpaired
3′ extensions on one pair staple at each end. Its hybridisation free energy is
the bias between the two states.

Defaults: 12 helices, 192 bp per arm (63.7 × 36.0 nm), 8 nt joint, 8 bp latch,
144 staples, 4632 of 7249 scaffold bases routed. No rule violations; the
warning profile matches the rectangle's.

Two things the constructor cannot establish, both stated rather than assumed:

- **Whether the latch can physically reach.** That depends on joint length, arm
  length and where the staple's 3′ end lands. It is a question for oxDNA, and
  it is the first thing the simulation pipeline should be pointed at. A latch
  that cannot reach produces a perfectly well-formed design whose measured bias
  is simply the unlatched one.
- **The conformational cost of closing.** Not predictable from sequence, and
  large. See below.

## The finding: Stage 0 could have returned nothing

The measurable bias is

    h = -(ΔG_latch + ΔG_conformational) / (2 kT)

Only the first term is sequence. The second is geometry, is identical across
constructs sharing a core, and is exactly what Stage 0's latch sweep measures
as an intercept.

A bulk FRET experiment reports a probability, and a probability near 0 or 1
carries almost no information about the free energy behind it: p = 0.999 and
p = 0.99999 are four kT apart and look identical through the noise. Taking
0.05 < p < 0.95 as informative, the window is **2.94 kT wide** in h.

Now the numbers. At 25 °C in 12 mM Mg²⁺:

| latch | ΔG₂₅ | h (sequence only) | p(latched) |
|---|---:|---:|---:|
| 4 bp, balanced | −3.48 kcal/mol | 2.93 kT | 0.997 |
| 6 bp | −7.95 | 6.71 | 0.999999 |
| 8 bp | −10.74 | 9.06 | ~1 |
| 10 bp | −15.21 | 12.84 | ~1 |
| 12 bp | −18.00 | 15.19 | ~1 |

One base pair is about **1.0 kT**. Stage 0's designed sweep of 5–10 bp spans
about 6 kT — but the conformational offset slides that whole span bodily
before any construct is read, and the window it must land in is 2.9 kT wide.
For most plausible offsets, **every one of the ten constructs reads p = 0 or
p = 1** and the stage returns no information for its €1,324.

`test_stage0s_own_latch_sweep_would_not_have_covered_anything` states this as a
test rather than a note.

## The fix: a bracketing ladder

Eight latches whose predicted fields are spaced no wider than the window, so
that whatever the offset is, one of them reads informatively. That rung locates
the offset; Stage 0's sweep is then placed around it.

| latch | bp | h |
|---|---:|---:|
| GATA | 4 | 1.39 kT |
| GATATAT | 7 | 4.09 |
| GCGCG | 5 | 7.02 |
| GCGACGC | 7 | 9.87 |
| GACTAGTCATGA | 12 | 12.74 |
| GCGCGCGCG | 9 | 15.61 |
| GCGCGACGCGC | 11 | 18.46 |
| GCGCGCAGCGCG | 12 | 20.60 |

Largest gap 2.92 kT against a 2.94 kT window: covered. It measures a
conformational cost anywhere from **0 to 44 kT**, which brackets any plausible
value.

**Cost: €307.** The ladder shares Stage 0's core and FRET pair, so only the 96
latch staples are new. The three stages together are €6,007, against €6,947 if
one naively adds the series costs — that difference is the shared core, and
`programme_cost_eur` is what stops it being double-counted.

Run it *before* ordering Stage 0, not alongside. Its output is which latch to
centre the sweep on; ordering both at once throws that away.

A run where no rung reads informatively is not a failed measurement. It says
the offset is outside the reachable range, and the **joint length**, not the
latch, is what has to change.

# Experiment roadmap

Seven experiments, four epics, one critical path. Per-epic detail is in
`roadmaps/`.

Costs are generated (`dobladillo.hamiltonian.experiments`), not estimated.
Scores are judgements and are marked as such.

## The sequence

| # | experiment | epic | relevance | difficulty | P(success) | ready? |
|---|---|---|---|---|---|---|
| **E1** | Rothemund rectangle, AFM | — | 5 | 1 | 0.90 | **yes, now** |
| **E2** | Twist pair | — | 4 | 2 | 0.75 | needs an AFM flatness observable |
| **E3** | Single hinge, fold check | 2 | 5 | 2 | 0.70 | needs a folded-hinge footprint prediction |
| **E4** | Bracketing ladder, 8 latches | 2 | 5 | 3 | 0.60 | needs `fret.py` |
| **E5** | Stage 0, 10 constructs | 2 | 5 | 3 | 0.55 | needs `equilibrium.py` |
| **E6** | Stage 1, 25 constructs | 2 | 5 | 4 | 0.35 | needs smFRET + ligation analysis |
| **E7** | Thickness ladder, 4 plates | 3 | 3 | 2 | 0.80 | needs a multi-layer plate part |
| **E8** | Patterned rectangle (hairpin F) | — | 4 | 2 | 0.65 | after E1: its Mg, reference height, a fold |
| **E9** | Rectangle dimer, assembly states | — | 5 | 3 | 0.55 | after E1: its Mg, reference height, plates |
| **E10** | Six-helix bundle, 3D fold | — | 4 | 3 | 0.60 | after the oxDNA run confirms it straight |
| **E11** | Isothermal folding screen (gradient block) | — | 4 | 1 | 0.80 | after E1: its magnesium, a fold, its pool |

**Relevance** — how much the programme moves if it succeeds, 1 to 5.
**Difficulty** — experimental, not computational, 1 to 5.
**P(success)** — a judgement with the dominant risk named in each roadmap, not
a calculation. Do not average these or treat them as calibrated.

## Critical path

```
E1 ──┬── E3 ── E4 ── E5 ── E6        the Hamiltonian line
     └── E2                          validates the lattice
E7                                   independent, different instrument
E1 ── E8 ── E9                       detail, then assembly (the user's roadmap, levels 3-4)
E1 ── E10                            first 3D part (level 6)
E1 ── E11                            folding window: fast, fixed-temperature folds
```

**E8–E10 came from the maintainer's own roadmap** (2026-09-28), which walks
from a first 2D fold to a closed computational loop. Level 3 there is a
pattern (E8), level 4 is assembly (E9) and level 6 is 3D (E10). Levels 1, 2,
5, 7 and 8 were already covered: E1 and its new positive control, E3–E6, and
the toolchain itself.

**E1 gates everything.** If a Rothemund rectangle — the most reproduced object
in the field — does not fold and image here, the problem is in our chain and
every later result would inherit it.

**E7 is off the critical path entirely.** Different instrument, different
question, no dependency on the hinge line. It can run in parallel with
anything, and it is the offer to the AFM partner rather than something we need
from them.

## The number worth saying out loud

Multiplying the critical path E1→E3→E4→E5→E6 gives **about 7%** of reaching a
validated two-spin Hamiltonian.

That is not an argument against doing it. It is an argument about where the
value sits: in E1 through E4, which are cheap and which each answer something
on their own, and in the fact that *failure at every stage is informative*.
E3 failing says a designed mechanism does not fold. E5 failing says
construct-to-construct scatter exceeds the couplings we want to measure, which
is a real result about DNA origami manufacturing. E6 failing says molecular
couplings are not pairwise, which is the most interesting negative result
available here and is publishable.

What would move the 7%: E3 succeeding at all (it is the least-evidenced link),
and the latch-reach question below.

## Open, and it blocks E3

The oxDNA joint sweep finished — 200 frames each at joint lengths 4, 8, 16 and
32 nt. Every one sits between fully closed (~64 nm) and flat (~131 nm), with
bend rising monotonically with joint length:

| joint nt | longest nm | bend nm |
|---:|---:|---:|
| 4 | 92.8 | 72.5 |
| 8 | 110.8 | 102.5 |
| 16 | 99.6 | 125.4 |
| 32 | 83.3 | 155.9 |

So the hinge bends, and the joint length controls how much. **It does not tell
us whether the latch reaches**, which is the question the sweep was launched
for, because that needs the distance between the two extension anchor points
and `analysis.observables` has no such measurement. See epic 2's roadmap.

## What happens after E6

The seven experiments stop at Stage 1, two spins. `HAMILTONIAN.md` continues to
Stage 2 (a chain of 4–6), Stage 3 (a plate of 25–100) and Stage 4.

Worth knowing while reading the table above: **none of E1–E7 uses the inverse
Ising solver.** Stage 0 is one probability; Stage 1's coupling is a closed-form
log-odds ratio. The solver first earns its keep at Stage 2 — and it cannot do
Stage 3 at all, by orders of magnitude rather than by a factor.

`roadmaps/stages-2-to-4-and-the-inverse-solver.md` has the measured scaling and
what Stage 3 would need instead.

## Before building M2 or M3

Both were named as if they were software to invent. Neither is: each is a
studied problem with a name, a complexity result and existing algorithms.
`roadmaps/m2-m3-what-the-literature-already-solved.md` says which, and the
headline is that staged assembly turns Θ(n) orthogonal interfaces into
O(log n) — an exponential saving in the thing that costs money here.

Neither blocks E1–E7.

## Money

| stage | constructs | cost |
|---|---:|---:|
| bracketing (E4) | 8 | €307 marginal |
| Stage 0 (E5) | 10 | €1324 |
| Stage 1 (E6) | 25 | €4376 |
| **all three, shared core** | **43** | **€6007** |

€6007, not the €6947 of adding the stages up: bracketing and Stage 0 fold the
same core. E1, E2, E3 and E7 are single constructs or small sets on cores
already counted.


## Project: the open AFM calibration kit (K series)

Planned 2026-09-29, after a literature review. It is a separate project with
its own series, not an epic of the Hamiltonian line. It reuses E1's rectangle,
E8's hairpin marks, E10's bundle and E11's isothermal fold. The goal is
an open kit: samples, protocol, software (`dobladillo calibrate`, being
implemented) and a certificate method. Everything else is in
[`projects/afm-calibration-kit/PROJECT.md`](../projects/afm-calibration-kit/PROJECT.md):
scope and non-goals, prior art (GATTAquant's GATTA-AFM and GATTA-AFM 3D,
Korpelainen et al. 2017, Raab et al. 2018, Kielar et al. 2020), risks, and
what partners would be asked for.

| # | experiment | needs | ready? |
|---|---|---|---|
| **K1** | software validation, synthetic and public data | `calibrate`, `calibration-tile` | no: both being implemented |
| **K2** | calibration tile: fold, purify, yield, marks | E1, E8; K1 for `calibrate` | after E1 and E8 |
| **K3** | lateral calibration, air and liquid, against a traceable grating | K1, K2 (E10 for the bundle arm) | after K2 |
| **K4** | tip reconstruction: tile and bundle against the GATTA-AFM 3D staircase; wear | K1, K2, E10 | after K2 and E10 |
| **K5** | preparation sensitivity (Mg, Ni, dry, deposition time) → the uncertainty | K3 | after K3 |
| **K6** | HS-AFM: scale, drift, hairpin against streptavidin marks | K3, HS-AFM access, a movie reader | blocked |
| **K7** | kit format and shelf life, 12 months | K3, K5 | after K5 |
| **K8** | certification against a traceable reference | K5, K7, a partner | the maintainer's decision |

```
E1 ── E8 ──┐
E11 ·······┤ (optional)
           K2 ──┬── K3 ──┬── K5 ── K7 ── K8     the reference line
K1 ─────────────┤        └── K6                 HS-AFM
E10 ────────────┴── K4                          tip
```

Not scored. Relevance, difficulty and P(success) are judgements for the
maintainer, and the K series is not yet in `dobladillo/programme.py`, so the
dashboard does not show it.

**How it meets the direction below.** K6 is this roadmap's first HS-AFM
experiment. What it establishes (scale and drift on an HS-AFM from all-DNA
fiducials, and how long the marks last under the tip) is what a
hinge-switching movie would need to be measured rather than watched.

## Direction: high-speed AFM

Recorded 2026-09-28, with no experiment yet, because no instrument is lined
up. Two uses, in order of promise:

1. **Watching the hinge switch.** A latched hinge opening and closing is
   isothermal by design, and it happens on timescales a high-speed AFM can
   follow. Its open/closed balance is the Ising field the whole hinge line is
   built to measure (E4-E6), so a direct trajectory would be a second,
   independent readout of the same number.
2. **Watching folding.** Needs a protocol that folds at a temperature the
   cell can hold, which is what E11 and `folding-window` are for; a
   magnesium jump or a denaturant washout at constant temperature are the
   alternatives. Caution: folding observed on mica is not folding in
   solution. The scaffold is adsorbed in 2D, which changes both the pathway
   and the speed, so it answers a different question.

A domain-level model of the folding process, which predicts which
temperature protocol folds fastest and where the traps are, is tracked
separately. It is to be implemented from the published method and validated
against E11.

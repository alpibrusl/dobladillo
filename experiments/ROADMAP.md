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

**Relevance** — how much the programme moves if it succeeds, 1 to 5.
**Difficulty** — experimental, not computational, 1 to 5.
**P(success)** — a judgement with the dominant risk named in each roadmap, not
a calculation. Do not average these or treat them as calibrated.

## Critical path

```
E1 ──┬── E3 ── E4 ── E5 ── E6        the Hamiltonian line
     └── E2                          validates the lattice
E7                                   independent, different instrument
```

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

# Epic 2 — the bistable hinge

[Issue #2](https://github.com/alpibrupa/dobladillo/issues/2). Four experiments,
E3 through E6, and the whole Hamiltonian programme runs through them.

The part is built and lints clean (`dobladillo build hinge`, `docs/HINGE.md`).
What is not established is whether it *works* — and that is four separate
questions, which is why this is four experiments and not one.

---

## E3 — a single hinge, folded and imaged

**Relevance 5. Difficulty 2. P(success) 0.70.**

Fold one hinge at the default 8 nt joint, run a gel, image it on mica. That is
all.

This experiment did not exist in the original plan, which went from "no hinge
has ever been folded" straight to an eight-construct ladder with a FRET
readout. Inserting it is the cheapest thing that can invalidate the entire
line: a hinge that does not fold, or folds into something that is not two arms
and a joint, makes E4 through E6 unorderable, and finding that out costs one
construct rather than eight.

**Gate.** A dominant gel band distinct from free scaffold, and AFM showing
two-armed objects. Not dimensions — *shape*. A hinge lying on mica is bent by
an unknown angle, so its footprint is not predicted (see below).

**P(success) 0.70, and the risk is the joint.** Eight unpaired scaffold bases
per helix across twelve helices is a large unpaired region, and unpaired
scaffold is where origami misfolds. If it comes back as aggregate, the first
thing to try is a shorter joint, which the sweep says is stiffer but still
bends.

### Software needed first

**A folded-hinge footprint prediction.** `compare` currently predicts the
hinge from its *arm* dimensions, which is what a flat, fully-open hinge would
measure. A real one on mica is bent, so its AFM footprint depends on an angle
nobody has measured. Options, cheapest first:

1. Report the two arms separately and compare each against 63.7 × 36.0 nm —
   the arms are rigid, only the joint is not. This needs particle segmentation
   to find two lobes rather than one, which `imaging.particles` does not do.
2. Predict the footprint as a function of angle and fit the angle. Better, and
   more work.

Option 1 is enough for E3's gate, which is about shape rather than size.

---

## E4 — the bracketing ladder

**Relevance 5. Difficulty 3. P(success) 0.60.**

Eight latches spanning 1.4 to 20.6 kT of predicted bias, spaced no wider than
the 2.94 kT window in which a FRET probability carries information. Whatever
the conformational offset turns out to be, one rung reads informatively and
locates it. **€307 marginal** — shares Stage 0's core and FRET pair.

This experiment exists because computing the predicted fields showed Stage 0's
own sweep could return ten saturated measurements and no information. See
`docs/HINGE.md`.

**Gate.** At least one rung with 0.05 < p(latched) < 0.95. If none does, the
offset is outside 0–44 kT and the **joint length**, not the latch, is what has
to change.

**P(success) 0.60.** Conditional on E3. The residual risk is that the latch
does not reach at all, in which case every rung reads p ≈ 0 and the ladder
correctly reports "outside the range" while the real cause is geometric.

### Software needed first

- **`hamiltonian/fret.py`** — bulk FRET to p(latched), with the calibration
  that makes it mean anything: donor-only and acceptor-only controls, direct
  excitation correction, the γ factor. `docs/STAGES_0_AND_1.md` says sloppy
  FRET calibration is the commonest source of a wrong free energy and that
  Stage 0's entire output *is* a free energy. There is currently no code for
  it at all.
- **A latch-reach observable.** Distance between the two extension anchor
  points over a trajectory. `_scadnano.nucleotide_indices` gives the mapping
  from design position to oxDNA index, so this is a small addition to
  `analysis.observables` — and it turns the finished joint sweep from four
  numbers about bending into an answer about whether the mechanism can close.
  **Do this first; it is cheap and it re-scores E3 and E4.**

---

## E5 — Stage 0, the forward map

**Relevance 5. Difficulty 3. P(success) 0.55.**

Ten constructs on a shared core, **€1324**: six latch lengths at balanced
composition, then four GC fractions at fixed length — the two axes swept
separately, because swept together a change in free energy could be either.
Centred on whichever rung E4 found.

**Gate: construct-to-construct spread below 0.3 kT.** Tightened from the source
document's ~1 kT, because at 1 kT a designed 1 kT coupling comes back with a
median error of 0.85 kT and Stage 1 could not then meet its own requirement at
any sampling depth.

What it really measures, and this is not how it is usually described: the
**intercept** of the latch sweep is the conformational cost of closing, which
no sequence model predicts and which is identical across constructs sharing a
core. Without it no predicted bias converts into an expected p(up).

### Software needed first

- **`hamiltonian/equilibrium.py`** — the two-initial-condition convergence
  test. Annealed from high temperature, and released from a locked state,
  confirming they converge. Otherwise the measurement is of kinetics, not of a
  Boltzmann distribution, and nothing in the numbers would say so. Declared
  mandatory in `docs/STAGES_0_AND_1.md`, currently no code.
- `fret.py`, shared with E4.

---

## E6 — Stage 1, two spins

**Relevance 5. Difficulty 4. P(success) 0.35.**

Twenty-five constructs, **€4376**. Six coupling mechanisms, the full 3×3 bias
grid on the medium strut, corners elsewhere. Two-colour smFRET for the joint
2×2 distribution, from which J follows as a log-odds ratio.

**The decision point of the programme.** The key plot is fitted J against
applied bias: horizontal is success, any slope means the couplings are
bias-dependent and the pairwise form is wrong.

**P(success) 0.35.** The lowest on the path and honestly so. It needs a partner
instrument, a molecular-biology collaborator for the ligation chemistry, and
three mandatory controls. A negative result here is a real finding about
molecular coupling and is publishable — which is why 0.35 is acceptable.

### Software needed first

- **Two-colour smFRET analysis** — the 2×2 joint distribution with its
  systematics. Larger than `fret.py` and partly the partner's stack.
- **Joint-state ligation controls.** Four constructs locked in all four *joint*
  states, not the two states of one spin. A per-spin bias is algebraically a
  field shift and cannot touch J (measured: 0.001 kT); only a joint-state bias
  can, and it adds exactly half itself. This is a design-side change, not just
  analysis.
- Sequencing counts: `hamiltonian/fit.py` already has `count_by_umi` and the
  nested-model comparison, so this one is partly done.

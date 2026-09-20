# Designed Hamiltonians in DNA Origami

**A staged experimental and theoretical program**

Status: draft v0.1
Companion to `DESIGN.md` (toolchain) and `APPLICATIONS.md` (application space). This document is the deep dive on one selected line: item C2 of `APPLICATIONS.md`.
Audience: project owner; implementing agents for the theory/software components; basis for a collaboration pitch once Stage 1 exists.

---

## 1. The question

**Not** "can we compute with DNA". The question is:

> Given a target probability distribution over discrete states, can the inverse problem of interface energies be solved, and does the physical system realise that distribution within measurable error?

This is an inverse Ising problem in which the couplings are **manufacturable** rather than inferred from data, and in which the forward map is only approximately the one written down. Synthesis error, sequence-dependent stacking, surface effects and undesigned correlations all enter.

**The scientific content is the discrepancy between the designed and the realised Hamiltonian.** Nobody has measured it for any molecular system, because nobody has been able to both design a Hamiltonian at this granularity and read out the full joint distribution.

In lattice-field-theory language: the action is set by chemistry; the question is how well the designed ("continuum") theory describes the physical ("discretised") one. The measured effective couplings are not the bare synthesised ones, and the difference is the physics.

### Framing discipline
Present this as designed statistical mechanics, **never** as computation. No optimisation benchmarks, no comparison to annealers, no MaxCut. Those comparisons are lost by six to ten orders of magnitude (see `APPLICATIONS.md` §5) and they attract the wrong reviewers.

---

## 2. The physical realisation

### 2.1 The spin
A **bistable hinge**: two rigid arms (n-helix bundles) joined by a short ssDNA joint, with two competing latch interfaces. Latch A closed → s = +1; latch B closed → s = −1.

- Bias h_i set by making one latch marginally more stable than the other.
- Tuning handle: latch length and GC content. ~1–2 kT per base pair.
- Usable range ≈ ±10 kT, in steps of ~0.5 kT → **effective weight precision 4–5 bits**. Thermal noise consumes the low end.
- Barrier height must be designed, not inherited: too low and the states aren't distinguishable; too high and it never equilibrates. Target ~8–12 kT.

### 2.2 The coupling — the hard part, and the real research question
Three candidate mechanisms, to be compared empirically at Stage 1:

| Mechanism | How | Expected strength | Range | Speed | Risk |
|---|---|---|---|---|---|
| **Mechanical (shared strut)** | two hinges share a rigid strut; state of A displaces B's latch site by a few nm, changing its effective ΔG | 1–3 kT | nearest neighbour only | fast (mechanical) | weak; may not exceed noise floor |
| **Steric occlusion** | A's arm occludes B's latch in one state | strong, binary-ish | very short | fast | geometrically fussy; hard to make *tunable* rather than on/off |
| **Strand-mediated competition** | a shared strand can bind A **or** B, not both | most tunable | longer (tether length) | slow (seconds) | leak; kinetic trapping |

Recommendation: build all three at Stage 1. The mechanical route is the most likely to give a clean, tunable, *additive* J; the strand-mediated route is the fallback if mechanical coupling is below the noise floor.

### 2.3 Lattice and connectivity
- 2D origami plate, hinges on a grid. Degree 4–6 nearest-neighbour coupling.
- Non-local coupling requires a tether long enough to reach → floppy, entropically costly, and it introduces its own conformational entropy into the Hamiltonian. **Treat long-range coupling as out of scope until Stage 4.**
- This planar, limited-degree connectivity is the same structural restriction that constrains quantum annealers. Acknowledge it rather than working around it; embedding overhead is a known and well-characterised cost.

### 2.4 Scale
- ~100 spins per plate is realistic: a 100 nm plate with hinges every ~10 nm.
- Copies: ~10¹⁰–10¹² per µL at nM concentration.
- **The parallelism is in the ensemble, not the device.** One plate is one sample; the ensemble gives the distribution.

### 2.5 Dynamics and the "clock"
- Barrier crossing at ~10 kT with ms attempt times → order seconds per flip.
- Annealing over a temperature or Mg²⁺ ramp → minutes.
- Equilibration must be **verified, not assumed** (see §6.3).

---

## 3. Readout — the underrated problem

Readout, not fabrication, is what limits the reachable system size. Three options, with very different scaling:

### 3.1 FRET — Stages 0–2 only
- Donor/acceptor pair across the hinge joint. Ratiometric, gives p(state) directly.
- **Limit: ~4 usable spectral channels.** Cannot read 100 spins.
- Bulk FRET gives ensemble averages ⟨s_i⟩; **smFRET** (TIRF, immobilised or in solution) gives single-molecule trajectories and hence *kinetics* as well as populations.
- Calibration required: donor-only and acceptor-only controls, direct-excitation correction, γ-factor. Budget real time for this; sloppy FRET calibration is the most common source of a wrong ΔG.

### 3.2 AFM / HS-AFM — Stages 1–3, structural validation
- Reads one plate at a time, slowly, **on a surface that biases the landscape**.
- Indispensable for confirming the structure folded and the hinges are where they should be. Not a route to the joint distribution at scale.
- HS-AFM additionally gives real-time flipping → direct kinetic measurement on a handful of molecules.

### 3.3 Proximity ligation + sequencing — the scalable route, Stage 3+
**This is the enabling technique for the whole program.**

- Design so that a ligation (or a primer-extension, or a proximity-dependent extension) event occurs **only in one hinge state**. The mechanical configuration is thereby converted into a sequence.
- Each spin gets its own barcode region; ligation joins barcode to a state-specific tag.
- Sequence the population → **the full joint distribution over ~10⁹ copies in one run.**
- Destructive. ~1 day and a few hundred euros per run.
- Nothing else gives the joint distribution of a many-spin system. This is why the program is possible now and was not before.

**Critical controls for the ligation readout:**
- Ligation efficiency must be measured **per state and per site**, and it will not be uniform. An unmeasured state-dependent efficiency bias is indistinguishable from a bias field h_i, and would silently corrupt every fitted parameter. Calibrate with constructs locked in known states (e.g. by a covalent crosslink or a permanently closed latch).
- PCR amplification bias: use UMIs (unique molecular identifiers) so each original molecule is counted once.
- Chimera formation during PCR creates spurious correlations between distant spins. Control with a mixed-population experiment: two separately locked populations mixed *before* amplification should show zero cross-correlation.

### 3.4 Readout choice by stage
| Stage | Spins | Primary readout | Secondary |
|---|---|---|---|
| 0 | 1 | bulk FRET | AFM (structure) |
| 1 | 2 | smFRET (2 colours) | AFM, HS-AFM (kinetics) |
| 2 | 4–6 | proximity ligation + sequencing | smFRET on a subset |
| 3 | 25–100 | proximity ligation + sequencing | AFM (structure QC) |
| 4 | 25–100 | as Stage 3 | field/temperature control hardware |

---

## 4. The experimental ladder

Each stage: purpose, construct, measurement, analysis, **go/no-go criterion**, and estimated cost.

### Stage 0 — The forward map, one spin

**Purpose.** Establish ΔG_eff(sequence) with error bars, and — more important — the spread across nominally identical constructs. That spread is the **manufacturing noise floor** and it sets the resolution of everything downstream.

**Construct.** Single hinge. Latch length swept over ~6 values (e.g. 5, 6, 7, 8, 9, 10 bp), GC content varied at fixed length as a second axis (~4 variants). ~10 constructs total, sharing a common staple core so only the latch staples change.

**Measurement.**
- Bulk FRET → p(up) as a function of temperature (25–45 °C) and [Mg²⁺] (8, 12, 16 mM).
- Repeat each construct as ≥3 independent folds, and ≥2 independent oligo syntheses for a subset, to separate folding variance from synthesis variance.
- AFM on each to confirm the structure.

**Analysis.**
- ΔG_eff = −kT ln(p_up / p_down).
- Fit ΔG_eff against nearest-neighbour prediction (SantaLucia); extract offset and slope. The offset is the origami-context correction — expect it to be non-zero and non-trivial.
- Variance decomposition: synthesis vs folding vs measurement.

**Go/no-go.** Construct-to-construct spread at fixed design must be **below ~1 kT**. If it exceeds that, couplings of 1–3 kT are unresolvable and the mechanical coupling route is dead; go to strand-mediated coupling, which is stronger, or stop.

**Cost.** ~€3–5k oligos (shared core keeps this low), ~2 months.

---

### Stage 1 — Two spins: can J and h be tuned independently?

**This is the decision point of the entire program.** Spend disproportionate effort here.

**Purpose.** Measure J. Then verify that J is **constant as h₁ and h₂ are varied**. If J and h are not independently tunable, there is no Hamiltonian — only a coupled mess — and the program stops.

**Construct.** Two hinges on one plate. Factorial design:
- Coupling mechanism: mechanical (3 strut lengths) × steric (1) × strand-mediated (2 tether lengths) = 6 coupling variants.
- Bias: h₁ ∈ {−2, 0, +2} kT × h₂ ∈ {−2, 0, +2} kT = 9 bias combinations.
- Full factorial is 54 constructs; **reduce to ~20** by taking the full bias grid only on the single best coupling variant, and a reduced grid (corners plus centre) on the others.
- Include an **uncoupled control** at every bias setting: two hinges on the same plate, far apart, no strut. Any measured correlation there is an artefact, and quantifies the background.

**Measurement.**
- smFRET with two colour pairs → full 2×2 joint distribution p(s₁,s₂).
- HS-AFM on the best variant → flipping kinetics, correlation times, and whether the two hinges flip independently or in a correlated way.
- oxDNA umbrella sampling on the same construct (see §5.3).

**Analysis.**
- J = ¼ ln[ p(++)p(−−) / p(+−)p(−+) ] — the log-odds ratio; this is exact for a two-spin Ising model.
- h_i from the marginals, corrected for J.
- **The key plot:** fitted J versus applied (h₁, h₂). A horizontal line is success. Any slope means the couplings are bias-dependent and the pairwise Ising form is wrong.
- Check additivity: does J(strut length) behave monotonically and predictably?

**Go/no-go.**
- |J| must exceed the Stage-0 noise floor by ≥3σ.
- J must be constant across the bias grid within ~0.3 kT.
- Uncoupled control must show |J| < noise floor.
- If all three hold → proceed. **If J drifts with h, stop and reconsider the coupling mechanism.** Publishable either way: a negative result here is a real finding about molecular coupling.

**Cost.** ~€8–12k oligos, ~4–6 months including instrument time.

---

### Stage 2 — A chain of 4–6: composability and undesigned terms

**Purpose.** First real test that couplings compose. And the more interesting question: **are terms needed that were not designed?**

**Construct.** Linear chain of 5 hinges with nearest-neighbour coupling, using the Stage-1 winning mechanism. Three designed parameter sets:
1. Uniform ferromagnetic (all J > 0).
2. Uniform antiferromagnetic.
3. A mixed/random set, fixed and known.

**Measurement.** Proximity ligation + sequencing → the full joint distribution over 2⁵ = 32 states, from ~10⁹ molecules. Plus smFRET on the end pair as a cross-check against Stage 1.

**Analysis.**
- Maximum-likelihood fit of a pairwise Ising model. Compare fitted (J, h) against designed.
- **Model comparison — the core of this stage.** Fit three nested models:
  - M1: nearest-neighbour pairwise only (as designed).
  - M2: + next-nearest-neighbour J.
  - M3: + three-body terms.
  
  Compare by likelihood ratio / AIC / BIC, with proper accounting for the sampling depth. **Any significant excess beyond M1 is the discovery.** Report its magnitude and its sign, and look for its structural origin (plate flexibility? shared staples? cooperative folding?).
- Validate the fit by predicting a held-out configuration's frequency.

**Go/no-go.** Fitted J within ~30% of designed, and residual structure either absent or *identified*. Proceed if the excess terms are small or explicable.

**Cost.** ~€6–10k oligos; sequencing ~€500/run × several runs; ligation chemistry development is the main unknown, so **budget time, not money, here** — and this is where a molecular biology collaborator becomes necessary.

---

### Stage 3 — 2D plate, 25–100 spins: the headline results

Two experiments, both worth doing.

#### 3A. Designed frustration
**Purpose.** Test the system against an **analytically known** answer.

**Construct.** Triangular lattice plaquettes, all couplings antiferromagnetic and equal. The ground-state degeneracy and residual entropy of the AF triangular Ising model are known exactly (Wannier). Start with a single plaquette (3 spins), then a 7-spin hexagonal cluster, then a larger patch.

**Measurement.** Sequencing readout of the full distribution.

**Analysis.** Measure the residual entropy and the ground-state degeneracy. Compare to the exact result. Look for the characteristic flat degeneracy of frustration versus symmetry-broken ordering, which would indicate undesigned anisotropy.

**Why this one.** Falsifiable against an exact theory, needs no fitted parameters to interpret, and makes a clean figure. Strongest single piece of evidence that the designed Hamiltonian is real.

#### 3B. Inverse design — the flagship number
**Purpose.** Close the loop: target distribution in, realised distribution out.

**Construct.** Pick a non-trivial target distribution over ~16–25 spins (e.g. one with designed multi-modality, or a specified correlation structure). Solve for (J, h) with the inverse solver (§5.1). Synthesise. Measure.

**Analysis.** **Report the KL divergence D(target ‖ realised).** That single number is the headline result of the program.

Also report: D(target ‖ ideal-Ising-at-fitted-parameters) to separate *design error* (the solver's fault) from *realisation error* (chemistry's fault). This decomposition is what makes the result interpretable rather than just a number.

**Cost.** ~€15–25k oligos; several sequencing runs; ~12 months.

---

### Stage 4 — Physics only this substrate gives

Two candidates; both are programs, not single experiments.

**4A. Designed disorder.**
Build a spin glass with a **chosen, known disorder realisation** rather than a random one. In simulation one averages over realisations; here the *same* realisation exists in ~10⁹ copies, so sample-to-sample variation and thermal fluctuation can be measured **separately**. That decomposition is hard to obtain any other way, and it is the clearest "why DNA" argument in the whole program.

**4B. Non-equilibrium steady states.**
Drive with an AC electric field (see `APPLICATIONS.md` §1) and measure how the stationary distribution departs from Boltzmann. Test fluctuation theorems on a many-body *designed* landscape, where the equilibrium reference is known by construction rather than fitted.

---

## 5. The theory and software programme

All of this runs on a laptop and a GPU while the wet lab is slow. **Build it first** — see §7.

### 5.1 The inverse solver
Target distribution → coupling matrix → sequences.

- The unconstrained pairwise case is **maximum entropy and convex**: standard, well-conditioned, solvable by gradient ascent on the log-likelihood with the model expectations from MCMC or mean-field/TAP for speed.
- The contribution is the **manufacturability constraints**:
  - J_ij must be realisable by some available strut length → a discrete, bounded set, not ℝ.
  - h_i quantised to ~0.5 kT steps over ±10 kT.
  - Connectivity limited by plate geometry (degree ≤ 6, planar).
  - Latch sequences must be mutually orthogonal (couples to `DESIGN.md` item M2).
- So: a **constrained, quantised inverse Ising problem**. Solve by projected gradient, or by relaxation followed by rounding with a repair step. Report the loss from quantisation separately from the loss from connectivity.
- This generalises well beyond DNA — any physical substrate with discrete, bounded couplings has this problem. Worth writing up on its own.

**Implementation:** `hamiltonian/inverse.py`. Deterministic, seeded, with synthetic-data tests (§7).

### 5.2 The discrepancy model
Hierarchical Bayesian: designed J → realised J.

Terms:
- synthesis error (per-oligo, from Stage 0 variance decomposition),
- sequence-dependent correction to the nearest-neighbour ΔG in origami context,
- surface bias (AFM-measured data only),
- ligation efficiency bias (per site, per state — from §3.3 controls),
- any excess coupling found at Stage 2.

Fit jointly across all stages, with stage-specific likelihoods. **This is what makes Stage N+1 predictable from Stage N.**

It is the same machinery as the yield model (`DESIGN.md` item C1). **Build them as one model**, with shared parameters for interface energetics. That coupling is an argument for doing both, and it saves duplicated work.

**Implementation:** `hamiltonian/discrepancy.py`, on NumPyro or PyMC.

### 5.3 oxDNA as the bridge
Three levels of description:

```
designed Ising  →  oxDNA coarse-grained  →  experiment
```

- For a two-spin construct, oxDNA + umbrella sampling along a hinge-angle / latch-distance collective variable gives the landscape **directly**, with no fitted parameters.
- Where **oxDNA agrees with experiment but disagrees with the Ising model** → the Ising model is wrong (missing terms, wrong functional form).
- Where **oxDNA agrees with the Ising model but disagrees with experiment** → the chemistry has something neither model captures (synthesis, surface, ions).
- Where **all three disagree** → something interesting; investigate.

This triangulation is far more convincing than any pairwise comparison, and it is cheap relative to wet-lab work.

**Caveat to record in every result:** oxDNA2 models monovalent salt only; Mg²⁺ enters as a high-[Na⁺] proxy. Latch stability is exactly the quantity most sensitive to this. Treat oxDNA couplings as *shapes* to compare, with an overall offset allowed to float.

**Implementation:** reuse `sim/` from `DESIGN.md`; add `sim/umbrella.py` and a collective-variable definition per construct.

### 5.4 Analysis stack
- `hamiltonian/fit.py` — maximum-likelihood Ising fitting from sequencing counts, with UMI-aware counting, bootstrap confidence intervals, and the M1/M2/M3 model comparison.
- `hamiltonian/fret.py` — FRET calibration (donor-only, acceptor-only, γ-factor, direct excitation) → p(state) with propagated error.
- `hamiltonian/equilibrium.py` — the two-initial-condition convergence test (§6.3).
- `hamiltonian/metrics.py` — KL divergence, residual entropy, correlation functions, with sampling-error corrections (naive plug-in entropy estimators are badly biased at these sample sizes; use a bias-corrected estimator and say which).

---

## 6. Failure modes, and how each is detected

Ranked by estimated probability.

### 6.1 J and h do not decouple (highest risk)
- **Detection:** Stage 1, the J-versus-bias plot.
- **Response:** switch coupling mechanism; if all three fail, the pairwise Ising form is not the right effective model — publish that, and reconsider whether a different state variable (e.g. a continuous hinge angle) gives a cleaner Hamiltonian.

### 6.2 Readout noise exceeds the coupling
- **Detection:** Stage 0 noise floor versus Stage 1 |J|.
- **Response:** strengthen coupling (strand-mediated), increase sampling depth, or accept lower weight precision and design only strong couplings.

### 6.3 The system is not equilibrated — measuring kinetics, not Boltzmann
**Subtle, and it would fool you if you were not looking for it.**
- **Detection:** approach the measurement from **two different initial conditions** (e.g. annealed from high T, and annealed from a locked state that is then released) and confirm they converge to the same distribution. Also vary the equilibration time by a factor of ~10 and confirm the distribution is unchanged.
- Make this a **standing control at every stage**, not a one-off.
- **Response:** lower barriers (shorter latches), raise temperature, or add a catalyst for strand exchange. Or reframe: if it cannot equilibrate, the system is a kinetically-controlled device, which is a different (still interesting) paper.

### 6.4 State-dependent ligation efficiency masquerading as a bias field
- **Detection:** the locked-state calibration constructs of §3.3.
- **Response:** measure and correct per site; include as a parameter in the discrepancy model.

### 6.5 PCR chimeras create spurious long-range correlation
- **Detection:** the mixed-locked-population control of §3.3.
- **Response:** fewer PCR cycles, UMI-based deduplication, emulsion PCR if severe.

### 6.6 Plate flexibility introduces global coupling
Every hinge sits on the same plate; plate bending could couple all of them weakly and non-locally.
- **Detection:** at Stage 2/3, an excess coupling that is **non-local and roughly uniform** rather than decaying with distance.
- **Response:** stiffer plate (more helix layers), or include a global mean-field term in the model and measure it — it may itself be an interesting result.

---

## 7. Sequencing of work — the efficient move

**Write the theory pipeline first, before any oligo is ordered.**

Generate synthetic data with oxDNA-derived couplings plus realistic noise (from literature estimates of synthesis variance and ligation bias). Then check:

- Can the inverse solver recover a known Hamiltonian from that synthetic data?
- At what sampling depth does the M1/M2/M3 model comparison become able to detect a three-body term of a given size?
- What noise floor makes a 1 kT coupling unrecoverable?

**If the pipeline cannot recover a known Hamiltonian from synthetic data with realistic noise, it will not work on real data.** Learning that costs nothing now and tens of thousands of euros later. It also produces the power analysis that any reviewer or funder will ask for.

Deliverable of this pre-stage: a short report giving the required sampling depth and noise floor per stage. That report is also the strongest possible attachment to a collaboration request.

---

## 8. Cost, timeline, odds

| Stage | Oligos | Other | Duration | Cumulative probability of reaching cleanly |
|---|---|---|---|---|
| Theory pre-stage | €0 | laptop + GPU | 1–2 months | — |
| 0 | €3–5k | FRET + AFM time | 2 months | 75% |
| 1 | €8–12k | smFRET, HS-AFM | 4–6 months | **40%** |
| 2 | €6–10k | sequencing ~€2k; ligation development | 6 months | 25% |
| 3 | €15–25k | sequencing ~€3k | 12 months | 12% |
| 4 | — | field hardware | open-ended | — |

**Publishability:** Stage 2 alone is publishable, including as a negative result. Stage 3B with a measured KL divergence is a strong paper in a good journal. Stage 4 is a research programme, not an experiment.

**Collaborator needs by stage:** Stages 0–1 need the AFM/biophysics partner (already in hand). **Stage 2 onward needs a molecular biology partner** for the ligation chemistry and sequencing — this is a different person from the AFM partner, and recruiting them is a Stage-1 task, not a Stage-2 one.

---

## 9. Instructions for the implementing agent

1. Build §5.1, §5.2 and §5.4 **before** anything wet-lab-facing. The §7 synthetic-data validation is the gate on everything else.
2. Share the interface-energetics parameters between the discrepancy model here and the yield model in `DESIGN.md` item C1. One model, two applications.
3. Never fabricate measurement data. If a stage's data is absent, generate the synthetic version, label it unambiguously as synthetic in both the filename and the file's metadata, and stop.
4. Every fitted parameter carries an uncertainty. Every entropy or KL estimate carries a sampling-bias correction, with the estimator named.
5. Record conditions (T, [Mg²⁺], [Na⁺], surface, equilibration protocol, oxDNA version) in the metadata of every result.
6. Keep the equilibration test (§6.3) as a standing check that runs on every dataset, not an optional analysis.

---

## 10. References to fetch and verify (not trusted from memory)

- Wannier 1950 — antiferromagnetic triangular Ising, residual entropy.
- Schneidman, Berry, Segev, Bialek, *Nature* 2006 — maximum-entropy pairwise models fitted to many-unit data; the methodological template for Stages 2–3.
- Jaynes 1957 — maximum entropy; Ackley, Hinton, Sejnowski 1985 — Boltzmann machines (for framing, not for method).
- Nguyen, Zecchina, Berg, *Adv. Phys.* 2017 — inverse Ising problem review.
- SantaLucia & Hicks 2004 — nearest-neighbour thermodynamics.
- Marras, Zhou, Su, Castro, *PNAS* 2015 — DNA origami mechanisms and hinge design.
- Gerling, Wagenbauer, Neuner, Dietz, *Science* 2015 — reconfigurable shape-complementary devices.
- Snodin et al. 2015 — oxDNA2; umbrella sampling with oxDNA (check current oxpy interface).
- Proximity ligation and molecular-configuration-to-sequence conversion methods — search current literature; this is the least settled technique in the plan and the one most worth a focused review.
- Paninski 2003 / Nemenman-Shafee-Bialek — entropy estimation bias at finite sample size.

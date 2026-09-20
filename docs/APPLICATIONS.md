# Driven DNA Origami: Realistic Application Space

Status: draft v0.1
Companion to `DESIGN.md` (toolchain). This document is about *what to build with it*.
Audience: project owner, and agents planning research direction.

---

## 0. The physics constraint that governs everything

At 10–100 nm in water: Reynolds number ~10⁻⁸, no inertia, thermal energy k_BT ≈ 4.1 pN·nm dominates every designed interaction. Forces are pN, not nN.

**You cannot push. You can only bias.**

Smoluchowski–Feynman: thermal noise cannot be rectified at a single temperature in equilibrium, regardless of how clever the geometry is. Directed motion requires **both**:

1. **Spatial asymmetry** — geometry (chiral obstacles, tapered channels, asymmetric binding sites) or composition (charge distribution, GC gradients, nanoparticle placement).
2. **Broken detailed balance** — a second temperature, a time-varying field, or chemical fuel.

Geometry alone → nothing. Drive alone → faster diffusion. The **product** is the machine.

Corollary for design: every device in this document must be specified as (asymmetry, drive) pairs, and every claim of directed motion must survive the question "what is the entropy sink?"

---

## 1. Drive modalities

| Drive | Timescale | Couples to | Addressable? | Infrastructure | Notes |
|---|---|---|---|---|---|
| **AC electric field** | µs–ms | backbone charge (origami is a stiff polyanion) | globally; locally with electrode arrays | microelectrodes on coverslip + function generator + amplifier | **Fastest by ~5 orders vs strand displacement.** Fights electro-osmosis and Joule heating; needs low salt, which conflicts with origami Mg²⁺ stability. Main compromise to solve. |
| **Plasmonic laser heating** | ns–µs | gold NP on the structure | **yes, single-site** | laser on the microscope, AuNP-modified staples | Local ΔT of tens of K within ~10 nm. Melts one addressed duplex without touching neighbours. Best spatial selectivity available. |
| **Temperature gradient (thermophoresis)** | ms–s | Soret coefficient: size, shape, charge density | by design, not in real time | microfluidic chamber + IR laser | A genuine two-bath system, so legitimately non-equilibrium. Cheap. |
| **Global T cycling** | s–min | all duplexes, by T_m | by designed T_m separation | thermocycler / Peltier stage | The "thermal instruction set" — see §3.2. |
| **Photoswitches (azobenzene)** | ms–s | duplex stability of modified domains | yes, by wavelength + placement | modified oligos (cost), LED/laser | Reversible, fuel-free, **no waste products**. Cost per modified oligo is the limit. |
| **Magnetic** | ms–s | attached bead | per-bead | magnetic tweezers | Bulky, but gives calibrated torque and force. |
| **Strand displacement** | s–min | specific domains | fully | pipette | Arbitrary logic, but slow and produces waste strands that accumulate. Good for *setting state*, bad for *dynamics*. |
| **pH / Mg²⁺ / ionic** | s | i-motifs, triplexes; global stability | no (global) | pipette | Useful as a master switch or a reset, not as an instruction. |
| **Chemical fuel (ATP, nicked-DNA, RNase)** | s–min | enzyme-coupled motifs | by motif | enzymes | Only true autonomous option; irreversible consumption. |

**Recommendation for a first setup:** AC electric field. Cheapest to build, fastest visible dynamics, and it pairs directly with HS-AFM so you can watch what you drive. Plasmonic heating second, if the partner's microscope already has a laser path. *Let the available instrument choose the first mechanism, not the other way round.*

---

## 2. Cross-cutting design primitives

These recur across every application below; build them once, in the registry.

- **Asymmetric rotor**: rotor arm + chiral obstacle on a pedestal. Ratchets an AC field into unidirectional rotation.
- **Bistable hinge**: two arms, ssDNA joint, two competing latch interfaces → double-well landscape, barrier tunable by latch length/GC.
- **T_m ladder**: a set of domains with separated melting temperatures (e.g. 35 / 45 / 55 °C) via length, GC content and designed mismatches. The addressing scheme for all thermal actuation.
- **Soret-tuned brick**: same interface set, deliberately different size/charge density → different thermophoretic mobility.
- **Plasmonic hotspot**: AuNP placed at a defined distance from a target duplex; defines a local actuation zone.
- **FRET reporter pair**: donor/acceptor across a moving joint. The default readout when AFM is unavailable (solution phase, ensemble or single-molecule).
- **Pulling geometry**: defined attachment handles for force spectroscopy on any interface.

---

## 3. Applications by domain

Each entry: **what**, **asymmetry + drive**, **readout**, **feasibility** (A = doable in this project's first 2 years with partner instruments; B = plausible with a funded consortium; C = frontier/speculative), and **honest limitation**.

### 3.1 Fundamental physics and metrology
*The strongest fit for this project's skill set. Prioritise here.*

**P1. Geometry-programmed Brownian ratchet — torque vs asymmetry curve** — **A**
- What: a designed series of rotors, sweeping obstacle geometry (chirality angle, height, gap) across ~10 variants; measure step statistics and stall torque for each.
- Asymmetry + drive: chiral obstacle + AC field.
- Readout: fluorophore tracking (TIRF) or HS-AFM.
- Why it matters: the rotary origami motor exists (Dietz/Simmel), but **the systematic torque-vs-asymmetry relation does not**. This is a clean physics result, and a toolchain that makes a 10-variant series cheap is precisely what makes it possible.
- Limitation: variants must share a staple core to keep oligo cost sane — design for this from the start.

**P2. Stochastic resonance in a bistable hinge** — **A**
- What: weak periodic drive + tunable noise; look for the switching-rate peak at non-zero noise amplitude.
- Asymmetry + drive: asymmetric double well + sub-threshold AC field; noise tuned by temperature or by added field noise.
- Readout: HS-AFM real-time flipping, or single-molecule FRET.
- Why: textbook nonlinear physics, never done in a *designed* molecular mechanism where the landscape is known a priori.
- Limitation: surface adsorption (mica) distorts both the well depths and the relaxation time. Must be controlled or done in solution by FRET.

**P3. Landauer / information ratchet ("molecular Maxwell demon")** — **C**
- What: read hinge state by FRET, apply a field conditioned on the reading, extract work; measure against the Landauer bound.
- Readout: FRET + force/position.
- Why: designed geometry gives a known landscape, which most demon experiments lack.
- Limitation: requires fast feedback electronics and a rigorous work accounting; a serious experimental physics project, not a side quest.

**P4. Calibrated nanomechanical test objects for AFM/force spectroscopy** — **A**
- What: structures of known geometry, tunable stiffness and designed rupture forces, distributed as reference samples.
- Readout: force spectroscopy; compare to oxDNA and to FE models.
- Why: **this is the offer to the AFM partner.** It gives them something independent of your research goals, and it fits the FAIR bioAFM databank agenda.
- Limitation: needs cross-lab validation to be a real standard; that is a consortium activity, not solo.

**P5. Direct test of fluctuation theorems (Jarzynski/Crooks) on a designed landscape** — **B**
- What: cyclic driving of a hinge or interface, work distributions forward and reverse.
- Why: DNA hairpins have done this; a designed origami landscape lets you *engineer* the barrier shape and test predictions across a family, not one molecule.

### 3.2 Computation and information
*Be careful here: DNA computing has been overclaimed for 30 years. Frame as physics, not as a competitor to silicon.*

**C1. Thermal instruction set — multiplexed T_m addressing** — **A**
- What: subsystems actuated one at a time by a global temperature ramp or a plasmonic pulse at a chosen AuNP. Composition is the addressing scheme (GC, length, mismatches).
- Asymmetry + drive: designed T_m ladder + temperature.
- Readout: FRET per channel, gel, or AFM.
- Why: a genuinely useful primitive for every other application in this doc — sequential assembly, staged actuation, error correction.
- Limitation: T_m separation of ~10 °C per channel caps you at ~4 channels globally; plasmonic addressing removes this cap but needs one AuNP per channel.

**C2. Programmable free-energy landscape as a physical sampler** — **B**
- What: interface energies *are* a designed Hamiltonian. The thermal bath performs Monte Carlo for free, in parallel across ~10¹⁰ copies. The equilibrium population distribution is the answer; read it out by sequencing, FRET, or AFM classification.
- Asymmetry + drive: designed interface energy matrix + annealing schedule.
- Why this one is flagged: it is lattice-model sampling in wetware, and the inverse problem (target distribution → interface energies) is exactly item C5 of `DESIGN.md`. Closest connection to the owner's lattice-field-theory background.
- **Honest limitation, state it in any pitch:** not competitive with GPUs for any problem anyone cares about; readout is slow and destructive. The interesting content is the physics of the energy→distribution mapping and the inverse design, not a speedup. Framed as physics it is a good paper; framed as "DNA computing" it joins a long line of overclaims.

**C3. Reconfigurable interconnect (the "nano-FPGA" question)** — **C**, see §5.
**C4. Stochastic/probabilistic computing primitives (p-bits)** — **B**
- A bistable hinge with a field-tunable bias *is* a p-bit: a stochastic binary unit whose flip probability is an analog input. Coupled p-bits do Boltzmann sampling and invertible logic.
- Limitation: coupling between units is the unsolved part — see §5.

**C5. Molecular data storage with mechanical (not sequence) readout** — **C**
- Information stored in hinge states rather than base sequence; rewritable, unlike sequence storage.
- Limitation: density is far worse than sequence storage and retention is poor. Interesting only as a physics demonstration of rewritable molecular memory.

### 3.3 Chemistry
**Ch1. Distance-controlled reaction cascades** — **A/B**
- Enzymes or catalysts placed at designed separations; measure rate vs distance. Origami's 5 nm addressability is the point.
- Drive: none needed for the static version; T or field to *modulate* spacing dynamically — that is the novel part.
- Limitation: enzyme attachment chemistry and orientation control remain artisanal (noted as a field-wide gap in `DESIGN.md`).

**Ch2. Mechanically gated catalysis** — **B**
- A hinge that occludes or exposes a catalytic site; field or light switches turnover on and off.
- Why: switchable catalysts with a *mechanical* (not chemical) trigger are rare.

**Ch3. Chirality-selective compartments** — **C**
- Chiral cavities of designed handedness for enantioselective binding or catalysis.

**Ch4. Thermophoretic separation / purification** — **A**
- Two bricks with the same interfaces but different Soret coefficients (by size, shape, charge density) separate under one gradient.
- **Immediately useful to the project itself** as a replacement for gel extraction between hierarchical assembly stages. Good early win: it pays for itself.

**Ch5. Dissipative (fuel-driven) assembly** — **B**
- Structures that exist only while driven and dissolve when the drive stops. Temperature cycling as the energy source, with ratcheting built into interface geometry: assembly favoured on the cold half-cycle, error removal on the hot half.
- Why it matters: **this is annealing-as-error-correction, formalised.** It attacks the p^(N−1) yield-decay wall that limits every large assembly (`DESIGN.md` §C1/C2), which is the single biggest practical obstacle in the field.

### 3.4 Biology and medicine
*High impact, high regulatory and stability cost. Realistic only with a biology partner.*

**B1. Mechanobiology force probes** — **A**
- Origami tension gauges or spring constructs presented to cells; measure receptor forces.
- Fit: **excellent** with an AFM/cell-mechanics lab. Lowest-friction entry into biology.

**B2. Ligand spacing arrays for receptor clustering** — **A/B**
- Vary ligand spacing at 5 nm resolution, measure receptor activation. Directly relevant to immunology and vaccine design.
- Limitation: needs cell culture and a biology collaborator; origami stability in serum requires coating (oligolysine-PEG, silica).

**B3. Nanopore and membrane channels** — **B**
- Origami-templated membrane pores with designed geometry, gated by field or light.
- Fit with a membrane-biophysics partner is natural.

**B4. Gated cargo containers** — **B/C**
- Logic-gated shells (the Douglas/Church lineage). Well trodden; differentiate only via *physical* gating (field, heat) rather than aptamer logic.

**B5. Therapeutics** — **C**
- Out of scope: stability, immunogenicity, manufacturing and regulation each exceed this project's resources. Listed only to mark it as deliberately excluded.

### 3.5 Energy
*Weakest domain. Be sceptical of anything promising useful power.*

**E1. Energy-transduction efficiency measurement** — **A/B**
- Not a power source: a *measurement* of how efficiently a designed ratchet converts field or gradient energy into mechanical work, vs the theoretical bound.
- This is the honest version of "DNA energy" and it is genuinely publishable.

**E2. Photon-to-motion via plasmonic heating** — **B**
- AuNP absorbs, local heating drives a conformational cycle. Efficiency will be dreadful; the interest is mechanistic.

**E3. Light-harvesting antenna arrays** — **B**
- Chromophores at designed spacings for directed energy transfer. Well studied by others; origami is the scaffold, not the innovation.

**E4. "Nanoscale power generation" for useful work** — **not viable**
- pN forces × nm displacements ≈ tens of k_BT per cycle at s⁻¹ rates. Nothing scales. Stated explicitly so it doesn't reappear in a proposal.

### 3.6 Materials and metamaterials
**M1. Origami-templated plasmonic metamaterials with switchable geometry** — **B**
- Chiral AuNP arrangements whose optical response switches with hinge state. Optical readout is easy and the effect is large, which makes this the most *demonstrable* dynamic application.

**M2. Mechanical metamaterials** — **B/C**
- Auxetic or negative-stiffness lattices from bricks. Requires the large-assembly capability of `DESIGN.md` §C2.

**M3. Origami-directed lithography** — **B**
- Patterning templates for semiconductor processes. Requires a cleanroom partner (e.g. CEA-Leti).

---

## 4. Prioritised shortlist

If only three things are attempted after the first closed loop:

1. **Ch4 — thermophoretic separation.** Cheapest, self-serving (improves the project's own purification), and gives an early non-equilibrium result.
2. **P1 — torque vs asymmetry curve.** The flagship physics result; the toolchain is what makes it feasible; publishable in a strong journal.
3. **C1 — thermal instruction set.** A primitive that unlocks P2, Ch5 and everything sequential.

Then: **P4** as the deliverable to the AFM partner, and **Ch5** as the long game against the yield wall.

---

## 5. Can we build a nano-FPGA?

Short answer: **not as an FPGA. The reconfigurability is achievable; the gain is not.**

An FPGA is (a) a sea of logic blocks, (b) a reconfigurable interconnect, (c) a configuration memory, (d) a clock. Taking them one at a time:

| FPGA element | Molecular status | Verdict |
|---|---|---|
| Logic blocks | seesaw gates, strand-displacement circuits, localised hairpin logic — demonstrated, incl. ~100-gate circuits and small neural networks | **Exists** |
| Configuration memory | hinge states, latched interfaces; rewritable | **Exists** |
| Reconfigurable interconnect | spatial rerouting of signals on a scaffold; no general implementation | **Missing** |
| Clock | global T or field cycling can synchronise | **Plausible** |
| **Signal restoration / gain** | — | **Missing, and this is the real blocker** |

**Why gain is the blocker.** An FPGA works because each gate restores its output to a full logic level; noise doesn't accumulate over depth. Strand-displacement gates are *consumed* by firing: one input strand produces one output strand. There is no amplification, so signal degrades with circuit depth and every gate is single-use. That is not a fabrication problem, it is the operating principle. Without restoration you cannot cascade deeply, and without deep cascading "FPGA" is the wrong word.

Catalytic amplifiers (hybridisation chain reaction, catalytic hairpin assembly) provide gain but are slow, leaky, and hard to localise — leak is the field's chronic problem.

**What is actually buildable, and worth building**

- **A reconfigurable analog/stochastic array, not a digital fabric.** Bistable hinges on a lattice = field-tunable p-bits. Couple them mechanically (shared struts) or electrostatically (proximity). The array then samples a Boltzmann distribution over its configuration space, and the "program" is the interface energy matrix plus the drive waveform. This is a **physical Ising/Boltzmann machine**, not an FPGA — and unlike an FPGA it plays to the substrate's strengths (massive parallelism, free thermal sampling) instead of fighting its weaknesses (no gain, slow, noisy).
- **Reconfigurable metamaterial rather than reconfigurable logic.** Switchable plasmonic arrays (M1) are a "field-programmable optical array" in a real sense, and the readout is trivially easy.
- **Field-programmable *matter*.** Bricks whose interface availability is switched by hinge state: the same brick set assembles into different structures depending on the applied program. That is the honest reading of "FPGA at nanoscale" — programmable *structure*, not programmable logic.

**Recommended framing.** Drop the FPGA analogy in any proposal; reviewers in this field have seen decades of silicon analogies oversold. Say "programmable stochastic array" or "physical Boltzmann sampler". The coupling mechanism between units is the open research question and the thing worth working on — it is the same unsolved problem as C4 above, and solving it would be a real contribution.

Nearest neighbours in the literature to check before committing: Qian & Winfree seesaw circuits and DNA neural networks; localised hairpin circuits on origami (Yin, Fan); Ising/annealing machines in other physical substrates (photonic, spintronic) for how such claims are properly framed and benchmarked.

---

## 6. Open questions

- The **low-salt vs Mg²⁺-stability conflict** for electric-field driving. Silica or PEG coating may decouple them; needs a literature check and probably an experiment.
- Surface adsorption bias: how much does mica distort every AFM-measured landscape? Needs a solution-phase cross-check (FRET) on at least one system.
- What is the *actual* efficiency bound for these ratchets, given the drive frequencies and the viscous drag? Compute it before building anything — it may kill E1/E2 on paper.
- Which measured quantity best constrains the yield model (`DESIGN.md` C1): end-point yield, rupture force, or melting curve? Probably rupture force, but it should be tested.

---

## 7. References to fetch and verify (not trusted from memory)

- Feynman, *Lectures* Vol. I ch. 46 (ratchet and pawl); Reimann, *Phys. Rep.* 2002 (Brownian motors review); Parrondo & Español on Smoluchowski–Feynman.
- Kopperger et al., *Science* 2018 — electrically driven origami arm.
- Pumm et al., *Nature* 2022 — DNA origami ratchet rotary motor.
- Gerling et al., *Science* 2015 — shape-complementary, temperature-switchable assembly.
- Qian & Winfree, *Science* 2011 — seesaw gates; Cherry & Qian, *Nature* 2018 — DNA neural network.
- Duhr & Braun, *PNAS* 2006 — thermophoresis of DNA.
- Kuzyk et al., *Nature* 2012 / *Nature Materials* 2014 — origami chiral plasmonics, switchable.
- Liedl / Tinnefeld groups — plasmonic heating and FRET rulers on origami.
- Collin et al., *Nature* 2005 — Crooks fluctuation theorem with single molecules.
- Bérut et al., *Nature* 2012 — Landauer bound experiment.
- Reviews on DNA nanotechnology stability in physiological conditions (coatings: oligolysine-PEG, silica).

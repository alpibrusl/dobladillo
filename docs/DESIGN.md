# dobladillo: design document

Status: draft v0.3. Audience: an implementing coding agent, plus the owner,
who runs the GPU jobs and the wet-lab work.

> **Section 9 of the source document is deliberately not reproduced here.** It
> records specific collaborations -- who to approach, in what order, and what
> each side gains -- which is strategy and personal information, and belongs
> outside the repository. The source document itself marks it as context for
> prioritisation rather than a task list.
>
> Published work is cited normally in section 12, including work by people who
> appear in that section: a paper is a paper. What is omitted is the
> collaboration framing around it, never the science.
>
> The operational consequence of section 9 is kept: **prioritise Q1-Q5 plus M4
> over everything else**, and do not contact anyone or draft outreach.

## 1. Purpose

Build an open, scriptable toolchain to design DNA origami **bricks** (reusable
parts with typed interfaces), compose them into larger assemblies and simple
stochastic mechanisms, predict their properties by simulation, emit everything
the lab needs, and ingest AFM/TEM images to close the loop between prediction
and experiment.

The gap being filled: existing tools design single structures (caDNAno,
scadnano, ATHENA) or simulate them (oxDNA, CanDo). Nothing offers a parts
library with characterised, composable interfaces and measured assembly yields.

**Long-term goal.** Programmable stochastic mechanisms and complex structures
assembled hierarchically from a standard brick set.

### Non-goals

- A GUI editor. scadnano and oxView already exist; we export to them.
- A new simulation engine. We wrap oxDNA.
- All-atom MD.
- First-principles prediction of folding yield or chemical stability. These are
  fitted to data or taken from literature tables.
- In vivo / therapeutic applications.

## 2. Principles

1. **Wrap, don't rewrite.** scadnano is the design data model, oxDNA the
   physics, NUPACK/ViennaRNA the thermodynamics.
2. **Everything is code.** A design is a Python script that produces a
   deterministic artefact. No hand-edited design files in the repo.
3. **Every prediction carries a comparison hook.** Any simulated observable
   must have a defined experimental counterpart (AFM dimension, hinge angle
   histogram, gel band, dimer yield).
4. **Reproduce before inventing.** Each tier starts by reproducing a published
   result.
5. **Human gates are explicit.** The agent never assumes a simulation was run
   or a structure folded; it consumes result files placed in `data/`.

## 3. Domain primer

The numbers in this section live in `dobladillo/constants.py`, each with its
source. If the two disagree, one of them is a bug.

### Geometry

| Quantity | Value |
|---|---|
| Rise per bp (B-DNA) | 0.34 nm |
| Helical repeat | 10.5 bp/turn |
| Helix diameter | ~2.0 nm; effective inter-helix spacing in origami 2.25 to 2.6 nm |
| Honeycomb lattice | crossovers to each of 3 neighbours every 7 bp (21 bp = 2 turns). Twist-neutral. |
| Square lattice | crossovers every 8 bp (32 bp = 3 turns, implies 10.67 bp/turn). Produces global right-handed twist unless corrected by periodic deletions. |
| Scaffolds | M13mp18 7249 nt; p7560; p8064. Sequences in `dobladillo/data/scaffolds/`. |
| Persistence length | dsDNA ~50 nm; 6-helix bundle ~1 to 3 um |

### Staple rules (hard constraints unless flagged)

- Length 20 to 60 nt, target 32 to 42.
- Each staple has at least one continuous binding domain >= 14 nt (seed).
- No binding domain < 5 nt.
- Avoid "sandwich" staples (short-long-short domain pattern) where possible.
- No staple crossover within 5 bp of a scaffold crossover on the same helix pair.
- Flag poly-G runs >= 4 and staples with strong predicted self-structure.

### Interfaces between bricks

- **Sticky-end**: staple extensions (typically 4 to 10 nt) hybridising to
  complementary extensions or to unpaired scaffold on the partner. Strength
  tunable by length/GC.
- **Blunt-end stacking / shape complementarity**: helix ends stack; geometric
  plugs and sockets give specificity. Strongly Mg2+ dependent, reversible.
- **Passivation**: any helix end not part of an interface must be passivated
  (poly-T tails, 4 to 8 nt, or scaffold loops) to prevent unwanted stacking and
  aggregation.

### Wet-lab defaults (for protocol sheets)

- Buffer: 5 mM Tris, 1 mM EDTA, 5 to 20 mM MgCl2 (screen in 2 mM steps), pH 8.
- Scaffold 10 to 20 nM, staples at 5 to 10x excess.
- Anneal: 65 C 15 min, then 60 -> 40 C at 1 C/h for 3D; 2D can ramp 1 C/min.
- Purification: agarose gel extraction, PEG precipitation, or 100 kDa spin filters.

### Simulation caveats

- oxDNA2 models monovalent salt only. Mg2+ is not explicit; the convention is
  to simulate at high [Na+] (0.5 to 1 M) as a proxy. Record this in every
  result's metadata.
- oxDNA length unit = 0.8518 nm. Convert in one place only (`units.py`).
- Origami need relaxation before MD: (1) energy minimisation with capped
  backbone force, (2) MD with mutual traps on paired bases, (3) trap release,
  (4) production.
- Reachable timescales are below most device actuation times. Use enhanced
  sampling (umbrella sampling, forward flux) for transitions, not brute force.

## 4. Architecture

```
design scripts (user / agent)
        |
  parts + compose      Brick, Interface, Assembly, compatibility checks
        |
  route + sequence     scaffold routing, staple breaking, connector design
        |
  scadnano model       canonical design representation
        |
  +--------+--------+
 export   sim      lab
(cadnano, (oxDNA   (IDT plates, pooling,
 oxView)   jobs)    protocols)
        |
  analysis <---- imaging    AFM/TEM ingest, particle stats
        |          |
        +-> compare <-+
              |
           registry (measured part + interface data)
```

### Core data model

- `Brick`: parametrised generator returning a scadnano `Design` plus metadata:
  lattice type, bounding geometry, list of `Port`s, free helix ends.
- `Port`: a location on a brick (helix set, end, orientation frame) with an
  `InterfaceType`.
- `InterfaceType`: kind (sticky / stacking / hybrid), geometry signature (which
  helices protrude or recess), sequence set, complement reference, predicted
  dG, measured yield (nullable).
- `Assembly`: graph of bricks (nodes) and port bindings (edges), with a
  hierarchical assembly plan (tree of stages).
- `Registry`: versioned store (YAML/JSON in repo) of bricks, interface types
  and measured data. **This is the long-term asset.**

### Checks on an `Assembly`

- Geometric: port frames compatible, no steric clash (coarse bounding volumes
  first, oxDNA later).
- Orthogonality: every connector sequence pair not intended to bind has
  predicted dG above threshold; computed across the whole assembly, per stage.
- Passivation: every unbound helix end is passivated.
- Expected yield: product over edges of measured (or default) interface yield,
  per stage.

## 5. Tech stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python >= 3.11 | type hints, ruff, pytest, mypy |
| Design model | `scadnano` Python package | verify current API for oxDNA and IDT export before relying on it |
| Simulation | oxDNA (CUDA build), `oxpy`, `oxDNA_analysis_tools` | run by human on local GPU |
| Format conversion | tacoxDNA | fallback if scadnano export is insufficient |
| Thermodynamics | pluggable `thermo.py` backends. **Default open source** = in-house SantaLucia nearest-neighbour duplex dG + `primer3-py` (GPLv2; hairpin, homo/heterodimer dG) + `seqfold` (MIT; ssDNA self-structure). **Optional academic** = NUPACK 4. | NUPACK is academic/non-commercial; ViennaRNA also restricts commercial use (verify). Core must run fully without either. Cross-validate the open backend against NUPACK once, and record the deviation. |
| Orthogonal sequences | own generator + `seqwalk` as candidate | |
| AFM ingest | `pySPM` / Gwyddion files, TopoStats as reference | |
| TEM | `mrcfile`, scikit-image; RELION/cryoSPARC for 2D classes stay external | |
| CLI | `typer` | |
| Packaging | `uv` or `pip` + `pyproject.toml` | |

## 6. Repo layout

```
dobladillo/
  parts/         brick generators (rectangle, nhb bundles, plates, hinge)
  interfaces/    interface types, sequence sets, compatibility
  compose/       Assembly graph, stage planning, checks
  routing/       scaffold routing, staple breaking, rule validators
  sequence/      scaffold assignment, connector design, thermo backends
  sim/           oxDNA export, input-file templates, job bundles, relaxation
  analysis/      trajectory observables (RMSF, twist, bend, angles, port frames)
  imaging/       AFM/TEM ingest, particle picking, measurement, yield counting
  compare/       prediction vs measurement reports
  lab/           IDT plates, pooling maps, pipetting sheets, protocol sheets
  registry/      YAML store + loaders
  data/scaffolds/ scaffold sequences
  units.py
  cli.py
designs/         one script per design, deterministic
data/            human-provided results: sim trajectories, images (not committed)
tests/
docs/
```

## 7. Roadmap

Each item: deliverable, acceptance criteria (AC), and whether a human gate (HG)
is needed.

### Tier 1: quick wins (pure software, days each)

**Q1. Project skeleton + scadnano round trip.** Repo, CI, lint, tests. Script
generates a 6-helix bundle (honeycomb) and a Rothemund-style rectangle (square
lattice, twist-corrected) with M13mp18.
*AC:* designs open in scadnano web and export to cadnano v2; scaffold length
accounting exact; tests pin staple count and lengths.

**Q2. Design-rule validator.** Implements all staple rules in section 3 as
composable checks returning structured violations.
*AC:* passes on published reference designs; seeded bad designs trigger each
rule; CLI `dobladillo lint design.sc`.

**Q3. Lab outputs.** IDT plate files (96/384), pooling map (which wells form
which part), pipetting sheet, folding protocol sheet with Mg2+ screen.
*AC:* plate file validates against IDT bulk-upload format; total nt and
estimated cost reported.

**Q4. oxDNA job bundle.** One command produces a self-contained directory:
topology, configuration, staged input files for the relaxation protocol in
section 3, run script, metadata JSON.
*AC:* bundle for the 6HB runs to completion on CPU in test mode (short steps);
human confirms on GPU. **HG**

**Q5. Baseline analysis.** From a trajectory: mean structure, RMSF per
nucleotide, end-to-end dimensions, global twist, bundle bend. Outputs JSON +
plots + oxView overlay file.
*AC:* 6HB and rectangle dimensions within 10% of literature values.

### Tier 2: medium (weeks each; first wet-lab loops)

**M1. Brick and Port abstractions.** Parametrised generators: n-helix bundles,
plates, a block. Ports with frames and geometry signatures. Registry v1.
*AC:* any brick instantiable from registry YAML; ports rendered in oxView.

**M2. Interface library v1 + orthogonality.** Sticky-end families (length, GC
classes) and stacking plug/socket patterns. Whole-assembly crosstalk matrix.
*AC:* generates >= 20 mutually orthogonal sticky interface types at stated dG
gap; crosstalk report per assembly; passivation check enforced.

**M3. Assembly composition + stage planning.** Assembly graph, geometric
placement via port frames, hierarchical plan (dimers -> tetramers), expected-
yield estimate, merged oxDNA export of a bound complex.
*AC:* two-brick dimer simulates stably with interface intact; planner output
lists pools and mixing order per stage.

**M4. AFM pipeline.** Ingest, flatten, particle segmentation, per-particle
length/width/height, classification into well-formed / malformed / aggregate,
monomer vs dimer counting.
*AC:* on human-supplied rectangle images, measured dimensions agree with a
manual measurement within 5%; yield numbers reproducible across scans. **HG**
Support both conventional AFM (static, in air or liquid) and HS-AFM movie
stacks; for stacks, track particles across frames and emit per-particle time
series. Read the partner lab's native file formats (Bruker, JPK/Bruker
NanoWizard, Nanosurf, ASD for HS-AFM) rather than requiring exported images. **Deliver as a standalone, separately usable module.**

**M5. Compare report + first closed loop.** Report joining predicted
observables with measured ones, writing results back into the registry.
*AC:* complete loop for (a) rectangle monomer, (b) one brick dimer with
measured dimer yield stored as interface data. **HG, first real milestone.**

**M6. One-DOF mechanism.** Hinge brick (two arms, ssDNA joint, optional strut
to set angle). Simulated angle distribution vs AFM/TEM angle histogram.
*AC:* predicted and measured mean angle within 10 degrees; distribution widths
compared and discrepancy documented. **HG**
With HS-AFM available, also compare *dynamics*: angle autocorrelation time from
movie stacks vs oxDNA. Note the surface-immobilisation caveat: mica adsorption
biases both the angle distribution and its relaxation, so record buffer, Mg2+
and surface treatment as part of the observable.

### Tier 3: challenging (months; research-grade, uncertain)

**C0. Interface rupture forces by HS force spectroscopy.** Pull single
brick-brick interfaces, measure rupture force vs loading rate (Bell-Evans /
Dudko-Hummer-Szabo fits) for energy-barrier positions and off-rates. Feeds C1
with physical parameters instead of only end-point yields. Needs a design with
defined pulling geometry; add a `pulling_geometry` field to `InterfaceType`.

**C1. Empirical yield model.** Fit interface yield as a function of interface
features (type, length, dG, geometry, Mg2+, temperature) from accumulated
registry data. Bayesian, with honest uncertainty. Needs dozens of measured
interfaces; design the experimental series to share staples across variants to
keep oligo cost down.

**C2. Hierarchical assemblies >= 8 bricks.** Planner optimises stage order and
purification points against the yield model. Target: finite 2x2x2 or ring
assembly with measured final yield vs prediction.

**C3. Free-energy landscapes for mechanisms.** Umbrella sampling / forward flux
wrappers around oxDNA for hinge, slider, bistable switch. Output: landscape
along a collective variable, barrier heights, predicted state populations.
Reduced Langevin model fitted to the landscape for long-time dynamics.

**C4. Multi-DOF coupled mechanisms.** Two or more coupled joints with designed
allostery. Beyond current published state of the art at good yield.
Exploratory.

**C5. Inverse design.** Given a target shape or landscape, search over
brick/interface choices. Only meaningful after C1 and C3 exist.

**C6. Actuation library.** Strand-displacement actuators with kinetic
estimates, salt/pH/light switches, annotated with measured switching times.

## 8. Validation strategy

| Level | What | Who |
|---|---|---|
| Unit | geometry, rules, file formats | agent, CI |
| Reference | reproduce published designs and their known dimensions | agent |
| Simulation | GPU oxDNA runs, results dropped in `data/sim/<design>/` | human |
| Experimental | folding, gel, AFM/TEM, images dropped in `data/img/<design>/` | human, via partner lab |
| Closed loop | compare report, registry update | agent, reviewed by human |

No Tier-2 item is "done" on software alone if it carries an HG.

## 9a. Companion documents

- `APPLICATIONS.md` — what to build with the toolchain: drive modalities, design
  primitives, applications by domain with feasibility grades, and an honest
  answer to the nano-FPGA question.
- `HAMILTONIAN.md` — the deep dive on one selected line, `APPLICATIONS.md` item
  C2: designing a Hamiltonian in origami and measuring the gap between the
  designed and realised one.

Both carry the same rule as this document: they are context for prioritisation.
Neither contains collaborator names, and the sequencing in section 9 governs.

## 10. Risks and open questions

- **Thermo licensing.** Resolved by design: the open-source backend is the
  default (NN model + primer3-py + seqfold); NUPACK is an optional backend used
  under an academic licence. primer3-py is GPLv2, so keep it an optional import
  if the project licence is to be permissive (MIT/Apache).
- **Mg2+ not modelled in oxDNA.** Stacking interfaces are the most
  Mg-sensitive, so their predictions are the least reliable. Measured data
  takes precedence.
- **Oligo cost.** Every new brick is ~EUR 500 to 1000 in staples. Mitigation:
  shared cores with swappable edge staples so new interfaces cost only tens of
  oligos.
- **Yield decay** with assembly size is the fundamental limit; the project's
  value depends on measuring it honestly, not on hiding it.
- **scadnano API drift.** Pin versions; wrap all scadnano calls in
  `dobladillo/_scadnano.py` adapters.
- Open: lattice choice for the standard brick set (honeycomb is twist-neutral
  and stiffer per helix; square packs denser and suits flat plates). Proposal:
  honeycomb for 3D bricks, square for 2D plates.
- Open: licence and publication strategy for the registry data.
- **Credit and IP with academic partners.** Instrument time is rarely free of
  authorship expectations. Agree authorship, data ownership and any
  Alpibru-held IP boundary in writing before the first joint experiment.
- **Instrument access is a favour until it is a grant.** The first loop runs on
  goodwill and a few hours of borrowed time; anything at the scale of C1
  (dozens of interfaces measured) needs funding and a formal collaboration.

## 11. Instructions for the implementing agent

See `AGENTS.md`, which is the working copy of this section.

## 12. Key references

To fetch and verify, not to trust from memory.

- Rothemund, *Nature* 2006: scaffolded DNA origami.
- Douglas et al., *Nature* 2009 and *NAR* 2009: 3D origami, caDNAno.
- Dietz, Douglas, Shih, *Science* 2009: twisted and curved shapes.
- Ke et al., *Science* 2012; Ong et al., *Nature* 2017: DNA bricks.
- Gerling et al., *Science* 2015: shape-complementary assembly.
- Wagenbauer, Sigl, Dietz, *Nature* 2017: gigadalton assemblies.
- Tikhomirov, Petersen, Qian, *Nature* 2017: fractal assembly.
- Praetorius et al., *Nature* 2017: biotechnological mass production.
- Snodin et al., *J. Chem. Phys.* 2015: oxDNA2. Poppleton et al., *NAR*
  2020/2021: oxView, analysis tools.
- Doty, Lee, Stérin, 2020: scadnano.
- Huang et al., *Nature Materials* 2021: MagicDNA.
- Kopperger et al., *Science* 2018: electrically driven robotic arm. Pumm et
  al., *Nature* 2022: ratchet rotor motor.
- Casuso, Redondo-Morata, Rico, *Phil. Trans. R. Soc. A* 2020: biological
  physics by high-speed AFM.
- Marras et al., *PNAS* 2015: DNA origami mechanisms (hinges, sliders).
- Bellot et al.: modification-free isothermal origami morphing by programmable
  staple-strand competition, with high-yield 2D and 3D transformations and
  **orthogonal reconfiguration of independent subdomains within a single
  scaffold** -- essentially the interface-orthogonality problem of item M2.
  Also an origami honeycomb 2D lattice as an imaging scaffold for cryo-EM.
  Fetch exact citations.
- Santiago, Simmel and co-workers: controlling and measuring linear and
  rotational motion of origami driven by external fields, with solution-phase
  readouts (nanoimpact electrochemistry, single-particle tracking on lipid
  bilayers). The motivation matters to this project: TEM and AFM require
  surface immobilisation and are therefore rather static, which is the same
  limitation items M6 and C3 run into. Fetch exact citations.

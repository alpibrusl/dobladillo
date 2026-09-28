# An end-to-end DNA origami toolchain, rebuilt: what to keep, what to replace

Written 2026-09-28, against the state of the field as of late September 2026
and against what building dobladillo actually taught — which is the better
evidence of the two, because every lesson below cost a bug.

The short version: **dobladillo reimplemented too much of the commodity layer
and too little of the layer nobody else has.** The silent failures clustered
in code that already existed elsewhere and was written again here. The things
that worked are the things no other tool does.

---

## 0. The constraint: open source, self-hosted, no external servers

Decided 2026-09-28. Every dependency must be open source under an OSI licence
and run on hardware we control. No web services in the loop — not for design,
simulation, analysis or publishing. It rules out several tools this document
first recommended, and the audit is worth keeping because the reasons are not
obvious from the papers:

| tool | licence | self-hosted | verdict |
|---|---|---|---|
| oxDNA, `oxpy`, `oxDNA_analysis_tools` | GPL-3.0 | yes — builds and runs on Apple Silicon CPU | **use** |
| AFMReader | GPL-3.0 | local library | **use** |
| TopoStats | GPL-3.0-only in its current `pyproject.toml` (LGPL-3.0 in older releases); but every release since 2.3.0 requires **topoly** (binary wheels only, no published source; PyPI says "Free for non-commercial use", its docs BSD-3-Clause), TensorFlow and Keras, and Python < 3.12 | local library | **excluded while it requires topoly** (checked 2026-09-28, #8); our flatten and segmentation stay |
| scadnano / caDNAno 2.5 | MIT / MIT-style | local | **use** |
| primer3-py | GPL-2.0 | local | **use** |
| Generative SNUPI (routing) | Apache-2.0, pretrained models in the repo | local | **use** |
| mrDNA | Illinois/NCSA (OSI) | needs a CUDA GPU | only on a GPU machine we host |
| CanDo | web server running Abaqus (commercial) | no | **excluded** |
| Off-Lattice CanDo | needs ADINA and MATLAB (commercial); off-lattice only | — | **excluded** |
| SNUPI (the predictor) | binary in a paper supplement, non-commercial | — | **excluded** |
| NUPACK | non-commercial academic only | — | **excluded** |
| NADOC | **no licence file** — public but all rights reserved | local | **excluded until licensed** |
| Nanobase.org | external server | — | local export format only; no upload |
| LegoGen (Aksimentiev group, DNA bricks) | not stated in its tutorial; a GUI with Blender built in | no licensed local release checked yet — treat as hosted | **excluded as a tool**; its method is below |
| NAMD / VMD (all-atom MD) | UIUC's own licences, free of charge but not OSI | local | **excluded**; GROMACS (LGPL-2.1) or OpenMM (MIT/LGPL) if all-atom is ever needed |

**What that leaves unfilled: a fast shape predictor.** Every fast option is
proprietary, unlicensed, a remote service, or needs CUDA. NADOC's local
Euler–Bernoulli beam model is the closest match and cannot be used without a
licence. So this is the one place where the rule in §3 — replace, don't
reimplement — inverts: **build a small beam finite-element predictor here**.

*Built 2026-09-28, `mechanics/beam.py`, `dobladillo predict`.* It is a
CanDo-class model: helices as beams on the lattice, crossovers rigid, and
stress from lattice twist and from deletions and insertions. It reproduces
composite-beam theory exactly (R = 168.0 nm for one shortened helix in a 6HB)
and runs in 0.3 s. **The criterion first written here was wrong for this class
of model.** It asked for the bent bundle's oxDNA arc to be reproduced, but
that arc comes from misphased crossovers, and a model that puts every
crossover on its lattice position cannot see phase. A first version tried to,
with springs at each crossover's backbone azimuth. It predicted the bent
bundles straight to within tens of microns, and it distorted correctly phased
designs, because published designs carry 17–22° of residual azimuth strain.
The split that works: `crossover_azimuth` catches misphasing, and the beam
model answers how far a correctly phased design bends and twists.
`predict` runs the azimuth check itself and marks its answer invalid when
phasing fails. **Still owed:** a physical reference for what the model CAN
see, meaning an oxDNA run of a deletion-bent bundle, or published curvature
radii (Dietz et al. 2009).

**When a tool is excluded but its method is known, implement it.** An
algorithm published in a paper is free to implement; code is not. Two
conditions, both from this project's own history:

1. **From the method, never from unlicensed code.** Implement from the paper
   and the textbook. NADOC's source is public and all-rights-reserved — do not
   read it into ours. The same goes for any repository without a licence.
2. **Every reimplementation ships with an independent reference.** The four
   worst silent bugs here were all in reimplementations — routing, index
   mapping, background fitting, alignment — and each was caught only by
   comparison against something not written here. A reimplementation without
   a reference to disagree with is how those bugs got in.

| excluded tool | its method | implement? | reference to validate against |
|---|---|---|---|
| CanDo, SNUPI, NADOC's beam model | finite-element beam model of the helix bundle, crossovers as constraints (Castro et al. 2011; Kim et al. 2012) | **yes, now** — nothing compliant fills the gap | our oxDNA trajectories: the bent bundle, the rectangle |
| NUPACK | McCaskill partition function over secondary structures | only if the missing `self_structure` rule needs it | primer3's hairpin and dimer calculations on the same sequences |
| mrDNA's ARBD engine | GPU Brownian dynamics | no — run mrDNA on a self-hosted CUDA machine if one exists | — |
| LegoGen | DNA bricks (Ke et al. 2012): 32-nt strands of four 8-nt domains, each domain a 90° turn on the square lattice. A shape is voxelised at 8 bp per voxel (2.5 × 2.5 × 2.7 nm) and each voxel is filled with brick domains | **later, not now** — no scaffold ceiling and trivially generated by an agent, but thousands of oligos, low yield on large shapes, days-long anneals, and nothing in E1–E7 needs it | Ke 2012's published cuboids; `routing.azimuth` applies unchanged |

**One idea from LegoGen to take now, independent of bricks: design variants
to share strands.** Its "residue map" pins sequences to lattice positions, so
changing one region of a shape leaves every other strand's sequence identical
and a strand library can be reused. The E4 ladder is eight hinges that differ
only in the latch, so it needs one shared pool plus eight latch pairs, not
eight full orders. Checked 2026-09-28: it already holds here, because staple
sequences follow from the scaffold and its rotation. Two latch variants share
130 of 132 staples, and `tests/test_hinge.py` now pins it.

**Licence of dobladillo itself: EUPL-1.2** (decided 2026-09-28). It is OSI
approved and copyleft, and its compatibility appendix lists GPL v2 and v3,
AGPL v3, LGPL, MPL 2, EPL and others — so it combines with every dependency
above, and a distribution that bundles GPL-3.0 code (oxpy, AFMReader) goes
out under GPL-3.0, as the EUPL's compatibility clause allows. The repository
previously declared MIT; that was replaced, and `tests/test_licences.py` now
fails on any dependency whose licence nobody has reviewed, any incompatible
licence, and any network import in the package.

---

## 1. What the bugs say

Every silent defect found in this project, by root cause. Silent means the run
completed and the numbers looked plausible.

| defect | what it looked like | root cause |
|---|---|---|
| bundle bent into a 269 nm arc; the "fix" left it at 4.9 body widths | plausible sizes in a table | **hand-written crossover routing** |
| traps file restrained the wrong nucleotides on any design with extensions | relaxation completed | **hand-written index mapping** |
| plane-fit background: 40 particles became 4 on a scan with bow | clean fixture results under 1% | **hand-written AFM processing** |
| Kabsch rotation transposed (earlier, caught) | superposition "worked" | **hand-written structural alignment** |
| production wrote 4 frames; RMSF quoted at 41% error with no flag | a finished run | our own sampling logic |
| energy trace wrote once; restart would redo finished work | a running job | our own bundle editing |
| thirty twisted sheets counted as nothing | a population that summed wrong | a fixed tuple of class names |
| `afm measure` reported 0% well formed on a good scan | a failed fold | comparing object to image |

The top four are **reimplementations of mature, published software** —
caDNAno's lattice rules, oxDNA's own analysis tools, TopoStats. Each was
written here to avoid a dependency, and each failed in a way the original had
already solved. The bottom four are in code only this project has, and those
were caught by the project's own discipline — pre-registration, refusal,
synthetic ground truth. That split is the argument of this document.

---

## 2. What has changed in the field (as of September 2026)

**Generative design exists now.** *Generative SNUPI* (Nature Communications,
2026) is a diffusion model that takes a user-drawn target shape and returns a
routed DNA origami, trained on equilibrium conformations from a multiscale
model; from over a hundred candidates, selected designs folded and showed
auxetic and modular behaviour. Algebraic approaches ("origami monoids",
bioRxiv 2025) and generative wireframe design (NAR 2025) sit alongside it.
Shape → routing is becoming a solved inference problem rather than hand work.

**Fast shape prediction is minutes, not days** — elsewhere. (None of the
tools in this paragraph is usable under §0; they are here as the state of the
art and as the published methods our own predictor follows.) CanDo and SNUPI are
finite-element models that minimise the stress a crossover pattern exerts and
predict bend, twist and flexibility directly — SNUPI reports bending and
torsional persistence lengths, and runs a 100 ns dynamic simulation of a
triangle in eight minutes on a laptop. mrDNA produces an atomistic structure of
a 7–8 kbp origami in under fifteen minutes. A graph neural network (Nature
Materials, 2024) predicts shape in seconds. oxDNA, by contrast, needs "day to
week scale" to equilibrate a deformable structure. Dobladillo used oxDNA for
every shape question and waited 6.5–13 hours per answer.

**AFM analysis is a maintained open-source stack.** *TopoStats* does
flattening, grain finding, molecule tracing and statistics for DNA on mica, and
gained a deep-learning segmentation path in 2026. *AFMReader* (January 2026)
reads the native formats this project said it could not: Bruker `.spm` and
`.jpk`, WaveMetrics `.ibw`, Gwyddion `.gwy`, high-speed `.asd`, WSXM; it
returns the image and the pixel-to-nm scale. Both are **GPL-3.0**, which is
fine for internal use and matters the day anything is distributed.

**Self-driving characterisation is arriving for AFM specifically.**
AEcroscopy and *AEcroscopyWave* (arXiv, July 2026) give programmatic control of
scanning probe microscopes for agentic use; label-free autonomous AFM driven by
synthetic data appeared in Nature Communications this year. Agentic
liquid-handling and protocol execution is an active 2026 literature. The bench
is beginning to have an API.

**Agent integration has a settled shape.** The MCP specification's July 2026
revision draws the line plainly: an *MCP server* gives an agent access to a
live system; an *Agent Skill* teaches it how to do a task. People have started
shipping DNA-design skills (a caDNAno-to-CanDo validation skill appeared on
GitHub this year). Nothing yet combines design, simulation, bench and
measurement behind one agent surface.

**What has not changed.** Every published tool still goes from a **shape** to
components. None goes from a **function** — an energy landscape, a switching
probability, a coupling — to components. And no tool closes the loop from a
prediction to a measurement with the conditions and definitions reconciled.

---

## 3. Replace, reuse, keep

### Replace with existing software

| layer | use | instead of our |
|---|---|---|
| lattice routing | caDNAno lattice rules via scadnano; Generative SNUPI (Apache-2.0) for free-form | hand-coded crossover offsets |
| fast shape | **none compliant exists** — build a beam FE model here (§0), validated against oxDNA; mrDNA on a self-hosted CUDA machine if one exists | oxDNA for every shape question |
| slow physics | oxDNA through `oxpy`, analysis through `oxDNA_analysis_tools` | our own Kabsch, RMSF, mean structure |
| AFM I/O | AFMReader | GSF-only reader and the Gwyddion export step |
| AFM processing | TopoStats (flatten, grains, tracing) | our flatten and segmentation |
| thermodynamics | primer3 (NUPACK is non-commercial, excluded) | our transcription of SantaLucia 1998 |
| sharing | a local, Nanobase-compatible export archive; no upload | nothing |

Each replacement keeps a thin adapter and the tests that caught our bugs. The
tests become conformance checks on the dependency: the bow scan, the
all-zeros GSF, the extension partition.

### Keep, and build out — the part nobody has

1. **The closed loop with definitions.** `compare` refuses to subtract a
   footprint from an extent, carries the salt proxy as a caveat, and separates
   size (3% allowance) from form (zero allowance). No published tool does this.
2. **The pre-registered record.** Predictions committed before data,
   git-timestamped, compared against at report time. This is what makes an
   agent-run experiment trustworthy, and it is new.
3. **Refusal over substitution.** No defaults for measured quantities; a
   missing tip radius stops the report. Generalise it (§4).
4. **Ports, channels and cross-talk.** The structural half of orthogonality,
   settled before any sequence exists.
5. **The programme as data.** Experiments, scores and blockers as typed
   records, rendered into a dashboard that cannot go stale.
6. **Function → components.** The Hamiltonian line: bias from latch
   thermodynamics, the bracketing ladder, the two-arm verdicts. This is the one
   inverse problem the field has not attacked, and it is where a paper is.

---

## 4. The architecture

```
spec ──▶ route ──▶ predict (fast) ──▶ verify (slow) ──▶ order ──▶ fold ──▶ image ──▶ compare ──▶ registry
         caDNAno   beam FE (ours,    oxDNA via oxpy    plates    bench or   AFMReader   ours      local
         SNUPI-gen validated vs      queued, parallel  [HUMAN]   handler    +TopoStats  (keep)    archive
                   oxDNA)
                   minutes           hours                       [HUMAN]    [HUMAN or
                                                                             agentic AFM]
```

**One provenance chain.** Every artefact is content-addressed and points at
its parent: design hash → prediction → simulation → order → experiment folder
→ scan → comparison. A comparison that cannot name the exact design and run it
came from is not reported. This is the custody pattern already used in
lex-docs, applied to a lab.

**Two speeds, on purpose.** The agent's inner loop must answer in minutes, or
it cannot iterate; the fast predictors are for that. oxDNA stays for what only
it does — hybridisation, thermodynamics, the latch — and runs queued and
parallel, never blocking the loop.

**Human gates as states, not comments.** Purchase, fold and image are explicit
states an agent can prepare and cannot pass. The agent writes the order and
the protocol; a person approves the spend. As agentic AFM matures, *image*
moves from a human gate to an instrument API, and the gate becomes an approval
of the session plan rather than of the scan.

---

## 5. Making it agent-friendly

Most of this exists already; the list is what to finish.

**Skill + MCP, per the 2026 split.** `SKILL.md` (generated, drift-tested)
teaches workflows and rules. An **MCP server** exposes the live systems:
simulation queue status and results, experiment folders and their `check`,
the parts registry, and — later — instruments. Today the agent reaches those
through the CLI; typed MCP tools remove the parsing and let the host show
approvals properly.

**Measured versus nominal, in the types.** The tip-radius rule generalises:
a `Measured[float]` carries its instrument, time and uncertainty; a `Nominal`
cannot be passed where a `Measured` is required. The refusal then happens at
the type boundary instead of in each command, and an agent cannot "helpfully"
fill a field with a catalogue value.

**Every stage has a synthetic twin.** AFM already does: scans of known
contents, with bow, drift and streaks, pinned in tests, and E1/E2 run end to
end before any sample exists. FRET needs the same, and so does the
fast-predictor stage. An agent that changes a stage is graded against its twin
before it touches a real run.

**A benchmark of known answers.** The Rothemund rectangle, a standard 6HB, and
published designs with their experimentally measured shapes — the
measurements as data, not the services that produced predictions for them.
Any change to routing or
prediction is scored against them. This is what would have caught the bundle
the day it was written.

**Refusals are data.** Every refusal has a stable `error.kind` and says what
to do instead. An agent that hits `no_tip_radius` should know the next action
is a measurement, not a retry.

**Nothing runs in the scratchpad.** Runs, queues and checkouts live in the
durable workspace; the session scratchpad is for scratch. Two sets of
simulation results were lost in this project to a cleaned temp directory.

---

## 6. What to do next, in order

1. ~~Build the beam FE predictor.~~ Built, and validated against textbook
   theory. It cannot see phase, so phase is the azimuth rule's job (see §0).
   Still owed: an oxDNA or literature reference for a deletion-bent design.
2. **Swap AFM I/O and processing for AFMReader and TopoStats**, keeping
   `compare`, `classify` and `arms` on top. Correct `PIPELINE.md`: native
   formats *are* readable, and the Gwyddion export step goes away.
   *AFMReader done (#7). TopoStats blocked (#8): it requires topoly, which
   ships no source and whose licence contradicts itself, plus TensorFlow and
   Python < 3.12; see §0 and `tests/test_licences.py`. Our flatten and
   segmentation stay.*
3. **Replace routing with the lattice's canonical crossover positions**, with
   the bundle as the first regression case.
4. **Use `oxDNA_analysis_tools` for alignment, mean structure and RMSF**, and
   keep ours only where they have no equivalent.
5. **Stand up the MCP server** over the queue, experiment folders and
   registry.
6. **Introduce `Measured`/`Nominal`**, starting with tip radius, magnesium
   concentration and temperature.
7. **Keep the Hamiltonian line on the critical path** — it is the part with no
   competitor — and run E1 and E2 at the bench, which are ready now.

---

## Sources

- Generative SNUPI: De novo design of DNA origami with a generative diffusion
  model, Nature Communications 2026.
  <https://www.nature.com/articles/s41467-026-73578-z> ·
  code <https://zenodo.org/records/19309767>
- SNUPI: A computational framework for rapid mechanical analysis of
  structured DNA assemblies, JACS Au.
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC12648286/>
- MrDNA, Nucleic Acids Research 2020.
  <https://academic.oup.com/nar/article/48/9/5135/5814051>
- Prediction of DNA origami shape using graph neural network, Nature Materials.
  <https://www.nature.com/articles/s41563-024-01846-8>
- How We Simulate DNA Origami, Small Methods 2025.
  <https://onlinelibrary.wiley.com/doi/full/10.1002/smtd.202401526>
- Generative design-enabled exploration of wireframe DNA origami, NAR 2025.
  <https://academic.oup.com/nar/article/53/2/gkae1268/7935005>
- Algebraic and generative design of DNA origami via origami monoids, bioRxiv.
  <https://www.biorxiv.org/content/10.1101/2025.09.13.675984.full.pdf>
- TopoStats. <https://github.com/AFM-SPM/TopoStats> ·
  Deep-learning-enhanced TopoStats, bioRxiv 2026.
  <https://www.biorxiv.org/content/10.64898/2026.05.06.723223v1>
- AFMReader. <https://github.com/AFM-SPM/AFMReader>
- AEcroscopyWave, arXiv 2607.22975. <https://arxiv.org/abs/2607.22975>
- Synthetic data-driven deep learning for label-free autonomous AFM,
  Nature Communications 2026.
  <https://www.nature.com/articles/s41467-026-70421-3>
- oxDNA and oxpy. <https://github.com/lorenzo-rovigatti/oxDNA> ·
  <https://lorenzo-rovigatti.github.io/oxDNA/oxpy/index.html>
- caDNAno crossover reference frames (scaffold and staple offset ~5 bp),
  Douglas et al., NAR 2009.
  <https://academic.oup.com/nar/article-pdf/37/15/5001/16752788/gkp436.pdf>
- generate-cadnano, a caDNAno-to-CanDo agent skill.
  <https://github.com/JLUNBBMS/generate-cadnano>
- MCP: Build with Agent Skills (2026-07-28 revision).
  <https://modelcontextprotocol.io/docs/2026-07-28/develop/build-with-agent-skills>
- Nanobase.org, NAR 2022.
  <https://academic.oup.com/nar/article/50/D1/D246/6423195>

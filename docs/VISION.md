# An end-to-end DNA origami toolchain, rebuilt: what to keep, what to replace

Written 2026-09-28, against the state of the field as of late September 2026
and against what building dobladillo actually taught — which is the better
evidence of the two, because every lesson below cost a bug.

The short version: **dobladillo reimplemented too much of the commodity layer
and too little of the layer nobody else has.** The silent failures clustered
in code that already existed elsewhere and was written again here. The things
that worked are the things no other tool does.

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

**Fast shape prediction is minutes, not days.** CanDo and SNUPI are
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
| lattice routing | caDNAno lattice rules via scadnano; Generative SNUPI for free-form | hand-coded crossover offsets |
| fast shape | CanDo / SNUPI / mrDNA / GNN | oxDNA for every shape question |
| slow physics | oxDNA through `oxpy`, analysis through `oxDNA_analysis_tools` | our own Kabsch, RMSF, mean structure |
| AFM I/O | AFMReader | GSF-only reader and the Gwyddion export step |
| AFM processing | TopoStats (flatten, grains, tracing) | our flatten and segmentation |
| thermodynamics | NUPACK or primer3 | our transcription of SantaLucia 1998 |
| sharing | Nanobase-compatible export | nothing |

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
         caDNAno   CanDo/SNUPI/      oxDNA via oxpy    plates    bench or   AFMReader   ours      Nanobase
         SNUPI-gen mrDNA/GNN         queued, parallel  [HUMAN]   handler    +TopoStats  (keep)    export
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
published CanDo examples with their measured shapes. Any change to routing or
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

1. **Re-diagnose the bundle with a fast predictor.** Export caDNAno JSON, run
   CanDo or SNUPI, and see whether they predict the arc. If they do, iterate
   routing in minutes against them — starting with scaffold crossovers along
   the length, which this design does not have. Only then spend an oxDNA run.
2. **Swap AFM I/O and processing for AFMReader and TopoStats**, keeping
   `compare`, `classify` and `arms` on top. Correct `PIPELINE.md`: native
   formats *are* readable, and the Gwyddion export step goes away.
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

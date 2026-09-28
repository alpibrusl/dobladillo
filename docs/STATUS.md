# Status

Mirrors the table in DESIGN.md section 11. One row per roadmap item.

| Item | State | Notes |
|---|---|---|
| Q1 project skeleton + scadnano round trip | done | both parts build, export to cadnano v2 and round-trip; accounting exact; counts pinned |
| Q2 design-rule validator | done | seven rules, each with a seeded failing design; `dobladillo lint`. `crossover_azimuth` (2026-09-28) replaced `crossover_phase` and is calibrated on five published designs in `tests/data/reference_designs`. `self_structure` declared unimplemented, not silently passing |
| Q3 lab outputs | done | IDT bulk CSV and plate xlsx, both validated; pooling map, pipetting sheet, protocol with Mg screen; cost estimate with assumptions |
| Q4 oxDNA job bundle | done | all four stages run to completion on CPU in test mode, zero errors. `sim.queue` now runs bundles several at a time: oxDNA's CPU backend is single-threaded, so one job used 1 of 16 cores |
| Q5 baseline analysis | done | parser, dimensions, RMSF, planarity, bend, oxView overlay; `dobladillo analyse`. Run on a real 200-frame trajectory: 328.2 +- 3.2 x 70.1 +- 4.0 x 17.7 +- 1.8 nm against a design of 390.4 x 8.0 |
| M1 Brick and Port abstractions | done | `interfaces/ports.py`: a port has a kind, a polarity, a width and a **channel**, and mates only within one. `crosstalk` reports every pair that would bind and was not asked to — the structural half of orthogonality, settled without sequences. Rectangle and hinge declare ports |
| M2 interface library v1 + orthogonality | todo | M1 settled the structural half. The sequence half is the **DNA word design problem** — decades of literature, standard constraints, formulated as maximum independent set. Design against a free-energy gap, not Hamming distance. See `experiments/roadmaps/m2-m3-what-the-literature-already-solved.md` |
| M3 assembly composition + stage planning | todo | This is **staged self-assembly** (Demaine et al. 2008): encode the shape in the staging algorithm rather than the tiles. One pot needs Θ(n) glues for an n×n square; staged needs O(log n). Its mix/split/store operations map onto combine/purify/store at a bench. Read it first |
| M4 AFM pipeline | done | flatten, segment, measure, classify, yield with a Wilson interval; validated to <1% against synthetic ground truth. Scans come in as Gwyddion Simple Field, and `dobladillo afm` is the CLI surface |
| M5 compare report + first closed loop | done | `dobladillo compare`: design against simulation against measurement, with the tip deconvolution that dominates any width. Validated by rendering a known rectangle through a modelled tip and recovering it. `docs/CLOSED_LOOP.md` |
| M6 one-DOF mechanism | part built | `parts/hinge.py`: two arms, ssDNA joint, latch. Re-tiled 2026-09-28 (see below); lints clean, 17 deg rms phasing strain. Simulation results from before the re-tiling describe the old design |
| C0-C6 | not started | research-grade |

Priority per DESIGN.md section 9: **Q1 through Q5 plus M4**, because those are
what make a first closed loop possible. Everything else waits.

## Decisions of 2026-09-28, applied

- **E1 and E2 were re-scaffolded** into `experiments/2026-09-28-rectangle-afm`
  and `2026-09-28-twist-pair`, and the old folders are marked SUPERSEDED.
  **Their gates are unwritten**, and `experiment check` says so; each plan
  quotes the old gate as a proposal.
- **E1 has a positive-control arm:** a bought known-good rectangle, imaged
  into `during/raw/control/`.
- **E4 has its two locked references:** `bracket` and `lab order
  hinge-locked-*`.
- **The staple rules are relaxed** to what published, folded designs contain.
  The benchmark passes, and the Nature 2009 and Dietz designs lint clean.
- **E8 (pattern), E9 (dimer) and E10 (3D bundle)** are being built.

## Benchmark, twins, thermodynamics, analysis (#14, #15, #10, #9)

- **Benchmark.** `dobladillo benchmark` scores the designs against sourced
  known answers:
  - published designs pass phasing;
  - the two bundle routings oxDNA showed bent fail it, and `predict`
    refuses them;
  - the current bundle passes;
  - composite-beam theory is reproduced.
- **First measured reference for the beam predictor:** Dietz 2009's 120°
  bundle, measured at 121 ± 8.4° (N = 212). The predictor gives **101°**
  with twist-stretch coupling, and 118° without it. This is recorded as a
  known failure, and the coupling term is the suspect.
- **Flagged under AGENTS.md rule 8:** `seed_domain`, `min_domain` and
  `staple_length` reject the Nature 2009 designs, which use 7-nt domains.
- **FRET twin and E4 dry run.** Bulk FRET needs locked-open and
  locked-latched reference constructs, and E4's order does not include
  them yet. `hamiltonian/fret.py` is still owed.
- **primer3 is the thermodynamics source.** `self_structure` remains
  unimplemented; if it is built, it will be McCaskill's algorithm,
  validated against primer3.
- **oat supplies alignment, mean structure and RMSF.** Our own code still
  computes extents, planarity, bend, reach and the sampling guard.
- **Quirk, not changed:** `bracket.ladder` computes at 1 M Na+ plus 12 mM
  Mg, not at 12 mM Mg alone.

## Agent access, provenance, AFM ingest (#11, #13, #19, #7, #8)

- **MCP server:** `dobladillo mcp`. E1's analysis runs end to end through its
  tools; refusals arrive with their `kind`; a real stdio session is tested.
- **Provenance:** E1 and E2 now carry the record problem "no design hash
  recorded", because both were re-tiled after their predictions were
  written. As a result, `experiment check` exits 1 on them. Whether to
  re-scaffold them is the experimentalist's decision.
- **Export:** local only. Publication fields are left for a person to fill in
  before any deposit, and simulation results are not exported yet.
- **AFM ingest:** native formats are read directly. Still open: a real
  partner file, with an independently known pixel size, committed as a
  fixture. Square pixels are assumed, not checked, for `.spm`, `.ibw` and
  `.gwy`.
- **#8 is blocked at the dependency:** TopoStats ≥ 2.3 needs topoly,
  TensorFlow and Python < 3.12. Re-check when topoly becomes optional
  upstream.

## Experiment record, typed (#18, #12)

- **E2's readout is a command.** `dobladillo experiment compare-arms <folder>`
  does what `experiments/protocols/e2_compare.py` did. It reads per-arm tip
  radii (before, between and after readings, plus `imaging_order`) and E1's
  reference height from `during/instrument.json`, and refuses when any is
  missing. It writes `post/arms.json` and states the verdict under both
  unblindings.
- **The tip-radius rule is enforced at the type boundary**
  (`dobladillo/readings.py`, `dobladillo/experiments/instrument.py`).
  `deconvolve_tip`, `experiment report` and `compare-arms` accept only
  `Measured` tip radii.
- **Still open:** `compare`'s default magnesium and temperature, and
  `afm measure`'s float tip radius.
- **The old script is still in the repository.** The E2 protocol no longer
  uses it.

## Where runs live (#16)

Runs, queues and trajectories live under `$DOBLADILLO_RUNS`, default
`~/Workspace/bio/dobladillo-runs`: outside the repository, because each
trajectory is hundreds of MB, and never in a temp directory. `sim bundle`,
`sim sweep`, `sim enqueue` and `sim run` warn on stderr when a path is under
one. On 2026-09-28 the only surviving bent-bundle trajectory (28/14) and the
two running reference runs were moved there from a session scratchpad. The
locally built oxDNA is at `~/Workspace/bio/oxDNA/build/bin/oxDNA`.

## Beam shape predictor (#22), 2026-09-28

`dobladillo predict <part|file.sc>`, 0.3 s per design. It is a CanDo-class
linear beam finite-element model (`mechanics/beam.py`), implemented from
Castro 2011, Kim 2012 and Gore 2006, not from anyone's code.

| check | reference | model |
|---|---|---|
| 6HB, one helix shortened 1/21 | composite-beam theory: R = 168.0 nm, toward that helix | 168.0 nm, toward it |
| crossover stiffness ×100 | rigid limit: no change | < 1% |
| rebuilt 6HB | straight | straight, 0° twist |
| E2 uncorrected arm | lattice arithmetic 309° (upper bound) | **+261° right-handed** |
| E2 corrected arm | ~0 | −21° |
| misphased bundles (oxDNA arcs 269, 347 nm) | — | straight: **cannot see phase**; `predict` marks these NOT VALID |

The E2 figure is new information, not a change to E2's recorded prediction,
which stays as written.

`predict` judges its own validity by crossover *placement* only
(`measure(count_skips=False)`). Deletions and insertions strain crossovers on
purpose; that is how a curved design bends, and the model handles it.

**Physical reference, running.** On 2026-09-28 an oxDNA run started on the 6HB
with a deletion every 21 bp on helix 0, using the same recipe as the bundle
runs. The model predicts R = 196 nm toward helix 0 (168 nm without
twist-stretch coupling). If oxDNA disagrees by more than its own
frame-to-frame spread, the model's parameters or its class are wrong for
designed curvature.

## Square re-tiling, 2026-09-28

Every square-lattice part put half its staple crossovers on the wrong face of
the helix. The tiling gave each helix two crossovers to the same neighbour
16 bp apart, and 16 bp is a turn and a half. `routing.azimuth` found it. It
takes the geometry from scadnano, splits strain into phasing and twist, and is
calibrated on designs we did not write:

| design | phasing rms | wrong face | twist |
|---|---:|---:|---:|
| published (Nature 2009 ×2, scadnano ×3) | 18–22° | 0 | as designed |
| old rectangle / twist pair / hinge | 89–91° | 46–48% | — |
| rectangle, twist pair (scadnano `origami_rectangle`) | 21°, 21°, 18° | 0 | 0, 0, −310° |
| hinge (`_lattice`, column parity) | 17° | 0 | 0 |
| six-helix bundle, 28/14 spans | 44° | 1% | 0 |
| six-helix bundle, scadnano's 6HB unit | 17° | 0 | 0 |

The uncorrected twist-pair arm's −310° matches the 309° predicted from the
lattice alone. That is an independent check on both.

- E1 and E2 order files were regenerated before any order was placed; each
  folder has `pre/RETILED.md`. Staple counts are unchanged, so pipetting stands.
- The hinge now has 132 staples, not 144; E3's protocol volumes are updated.
  **The hinge joint sweep and latch-reach runs above were made on the old
  tiling** and need re-running before they inform E3 or E4.
- The bundle was misphased too (44°). It now tiles scadnano's published 42-bp
  unit (17°). Whether that removes the oxDNA arc is running now; see
  docs/BUNDLE_BEND.md.

## Q4: verified, and what it took

**All four stages now run to completion on CPU in test mode**, with zero errors and
every configuration and trajectory produced. Getting there took two fixes, both
of which only appeared by executing the bundle rather than inspecting it.

oxDNA was built here from v3.7.0, CPU only (this is an Apple M4 Max: no CUDA,
and oxDNA's GPU backend is CUDA; a Metal backend exists only as an unmerged
pull request, on hardware with no fp64 at all).

A test-mode bundle for the six-helix bundle runs stages 1, 2 and 3 to
completion and chains correctly through their configurations. Stage 4 stops
with:

    ERROR: Distance between bonded neighbors 2939 and 2940 exceeds
    acceptable values (d = 1.065426)

That is oxDNA behaving correctly, not a malformed bundle. Stages 1 to 3 carry
`max_backbone_force` caps, which tolerate a stretched backbone; production
carries none, so it refuses to start on a structure the short test-mode
relaxation has not finished relaxing. The lesson is worth keeping: **the
documented relaxation is not a formality, and how much of it a structure needs
is measurable rather than assumable.** How many steps are actually required was then measured: at 1000 trapped MD
steps production refuses, at **20000** that error is gone. Test mode now uses
that floor, since a shorter test would only ever prove that production fails.

Raising it surfaced a second, unrelated defect. Production then died with
"Aborting because the program is generating too much data (1.47 MB/s)": a
configuration of this structure is about 4 MB and the stages printed one every
steps/10, which on a short stage is a torrent. oxDNA aborts above 1 MB/s. The
bundle now fixes the NUMBER of configurations per stage rather than the
interval, so the output rate falls as stages lengthen instead of rising.

## Epics

Opened after reading `APPLICATIONS.md` and `HAMILTONIAN.md`. Four, deliberately:
those documents contain a great deal that is worth doing eventually, and
`DESIGN.md` §9 warns in its own words that a many-tier plan with no data reads
as ambition without evidence.

- **#1 the theory pipeline and its synthetic-data gate** — do this first. Pure
  software, runs here, and it is the gate on tens of thousands of euros of
  oligos.
- **#2 the bistable hinge** — the one part three documents converge on, and the
  first whose prediction is a distribution rather than a shape. **Built**:
  `dobladillo build hinge`, no rule violations. Building it produced the
  finding in `docs/HINGE.md` — Stage 0's latch sweep could have returned ten
  saturated measurements and no information.
- **#3 calibrated nanomechanical test objects** — the offer to the AFM partner,
  and much cheaper than the roadmap assumes now that nanoindent exists. The
  experiment is `docs/PLATE_INDENTATION.md`; the offer turned out to be a
  better one than planned, because the calibration is modulus-independent.
- **#4 AFM ingest** — M4's remaining half, with no file readers to write.

Not opened, and why:

- **`APPLICATIONS.md` tiers B and C** (therapeutics, metamaterials, nanopores,
  lithography, the information ratchet) need partners and instruments that do
  not exist yet. An epic for each would be a wish list.
- **`HAMILTONIAN.md` stages 2 to 4** are gated on wet-lab results AND on a
  molecular biology partner for the ligation chemistry, who the document itself
  says should be recruited during stage 1. Opening them now would schedule work
  behind a person who has not been asked.
- **The nano-FPGA question** (`APPLICATIONS.md` §5) is an answered question, not
  a task. The answer is no, and the document explains why: there is no signal
  restoration, so depth cannot cascade.
- **Ch4, thermophoretic separation** is first on the applications shortlist and
  genuinely self-serving, but it is a wet-lab technique with almost no software
  content. Worth doing; not worth an epic here.

## Running experiments

`experiments/` holds one folder per experiment, in three phases: `pre/` fixed
before the first sample exists, `during/` what actually happened and the raw
files, `post/` produced by the toolchain. `dobladillo experiment new` scaffolds
one and `experiment check` reports whether its record can be believed.

The mechanism, rather than the folders, is **pre-registration**. `compare` will
reconcile a measurement with whatever is predicted, and a prediction adjusted
after seeing a scan produces output identical to one made in advance -- nothing
in the numbers distinguishes them. So the distinction lives in the record:
`pre/prediction.json` is committed before the session, `check` compares its git
commit time against the first raw file's, and `post/` compares against the
recorded prediction rather than a freshly computed one.

Timestamps come from git rather than the filesystem, because cloning resets
every mtime to the moment of checkout and a naive check would pass for
everyone while meaning nothing.

`experiments/2026-09-22-rectangle-afm` is scaffolded and ready, with the gate
transcribed from `docs/AFM_FIRST_TRIAL.md`.

`experiments/AGENTS.md` scopes an assistant working there: it may run commands
and draft an interpretation; it may not write the gate, edit the prediction,
touch a raw file, or fill in a number an instrument should have produced. That
last rule is enforced rather than asked for -- `experiment report` refuses a
missing tip radius and `compare` takes `--tip-radius` with no default -- because
a guessed radius removes 8.7 nm from every width and nothing downstream can
tell.

## The two runs that finished

**Six-helix bundle, 1M production steps, 200 frames.** 328.2 ± 3.2 × 70.1 ± 4.0
× 17.7 ± 1.8 nm against a design of 390.4 × 8.0, with 51.5 nm of axis bend.
**Found: a real design defect.** Not under-relaxation (the bend is stationary)
and not thermal (sd 2.7 nm on a mean of 51, and the direction is fixed in the
body frame at order parameter 0.993). Every crossover in the bundle sits at
phase 0 mod 21, so each helix bonds both neighbours at one backbone azimuth
while they sit 120° apart — a constant azimuthal strain around a ring, which
is a constant bend. Radius 269 ± 11 nm. See `docs/BUNDLE_BEND.md`.

A rule `crossover_phase` catches identical phase sets, and the routing was
changed to 28/14 spans to satisfy it. **That did not straighten the bundle**:
a 200-frame production run of the rebuilt design gives sagitta 49.9 nm, 4.94
body widths, order parameter 0.995 — the same arc. The phasing diagnosis is
refuted, the rule was necessary and not sufficient, and the next step is a fast
finite-element predictor rather than another hand-written fix. See
`docs/BUNDLE_BEND.md` and `docs/VISION.md`.

This also settled the sampling fix. The same run read at four frames gave a
middle extent of 48.3 ± 22.6 nm; at 180 frames it is 70.1 ± 4.0. The four-frame
answer was wrong by 45% and its error bar did not cover the truth.

**Hinge joint sweep, four lengths, 200 frames each.** Bend rises monotonically
with joint length — 72.5, 102.5, 125.4, 155.9 nm at 4, 8, 16 and 32 nt — and
every joint sits between fully closed (~64 nm) and flat (~131 nm). It still
cannot say whether the latch reaches; see the table below.

## What is blocking which experiment

`experiments/ROADMAP.md` has the sequence and the scores; the short version of
what software is owed, cheapest first:

| needed | blocks | size |
|---|---|---|
| ~~latch-reach observable~~ | done: `observables.reach`, and it found a silent index bug | — |
| ~~flatness observable~~ | done: `twisted` is its own class, on height | — |
| folded-hinge footprint prediction | E3's gate | medium |
| `hamiltonian/fret.py` | E4, E5 | medium |
| `hamiltonian/equilibrium.py` | E5 | medium |
| multi-layer plate part | E7 entirely | large |
| two-colour smFRET + joint-state ligation controls | E6 | large |
| sampling-based inverse solver (pseudolikelihood/MCMC) | Stage 3, beyond E6 | large |

The latch-reach observable is the highest value per line: it converts the
finished joint sweep from four numbers about bending into an answer about
whether the hinge can close, which re-scores two experiments.

## What M1 found on its first run

A film of N hinges sharing one latch sequence is **not N switches**. Every
latch binds every other latch — three hinges give six cross-talk pairs — so it
is one interface asked to mean N things, and no sequence optimisation fixes
that because they *are* the same sequence.

This invalidates arithmetic done before the module existed. `docs/COMMERCIAL.md`
costed a 3×4 coupled film as twelve hinges on one shared core, which is right
about the scaffold and wrong about the interfaces: it needs **twelve orthogonal
latch channels**, not one latch. That is a different and harder design problem
than the bracketing ladder, whose eight rungs differ in *strength* rather than
in *identity*.

The commercial case for that film was already withdrawn on other grounds, so
nothing downstream changes. It is recorded because the same mistake is
available to anyone composing bricks, and `crosstalk` is now what catches it.

## Shape on the dashboard

`dobladillo dashboard --runs <dir>` draws each part's simulated outline against
its design. Checked against the bundle's own trajectory, the envelope recovers
a centreline sagitta of 50.2 nm on a body 10.7 nm thick — the arc that a table
of length, width and height had not shown anyone.

## The index bug the reach observable found

`nucleotide_indices` skipped extensions **without advancing its counter**, so
every particle after one carried an index too low. The hinge's two 8 nt latches
left the map 16 short of the topology's 9184.

That map is what `sim.mutual_traps` builds its traps file from, so relaxation
of any design with extensions restrained the wrong nucleotides. It is silent by
construction: the run completes, the numbers are plausible, and nothing says
the restraints were on the wrong particles.

**The joint sweep was run with it.** Its four production trajectories carry no
traps, so the production physics is sound, but each started from a
configuration relaxed against wrong restraints. Treat those bend figures as
indicative rather than settled; the sweep is cheap to repeat now.

`extension_indices` gives the unpaired particles, and a test asserts the two
maps partition the topology with nothing missed and nothing counted twice.

## Flatness, and which measure actually works

E2 needs *what fraction lies flat as a clean rectangle*, apart from what
fraction is the wrong size — the two say opposite things about the design.
`classify` has a fourth class, `twisted`: right footprint, wrong height
profile. Verified against ground truth at 30/30, 20+20 and 30/30.

The measure that decides it is **height**, and the intuitive choice is wrong
twice. A rolled sheet's median sits on its ridge, so height goes 2.00 → 2.97.
Roughness also moves, and on a quiet image it moves *more* — 3.8× against
height's 1.5× at 0.06 nm of noise. But roughness's baseline **is** the noise,
so its separation collapses to 1.2× by 0.30 nm while height's holds at 1.49 –
1.51 throughout. Roughness is kept as a secondary signal for the one thing it
alone sees: a fold or tear that does not lift the median.

`Particle` also gained `rectangularity` — filled area over its own bounding
box — which is what separates "the right size" from "the right shape".

## E2 is ready

`imaging.arms.compare_arms` is the readout: the difference in flat fraction
between the two arms, with a **Newcombe** interval on the difference rather
than a Wilson interval on each. Quoting the per-arm intervals and eyeballing
the overlap is a known way to call a real difference insignificant, and there
is a test of a case where the arms' intervals overlap while the difference's
excludes zero.

Three verdicts, and the third is not a shrug. `indistinguishable` means the
twist correction is unnecessary and comes out of every square-lattice design —
which `docs/TWIST_PAIR_EXPERIMENT.md` names as the interesting outcome. There
is also `distinguishable but immaterial`, because at n=400 a two-point
difference clears zero and still does not justify deleting one base in every
sixty-four from every design.

`experiments/2026-09-23-twist-pair` is scaffolded with **both** arms ordered —
the scaffold command builds one part, and a matched pair is one experiment with
two constructs.

## Direction

`docs/VISION.md` (2026-09-28) sets out what to replace with existing software
and what to keep. The short form: the four worst silent bugs here were all in
reimplementations of mature tools — routing, index mapping, AFM processing,
alignment — and the parts that worked are the ones nobody else has.

## Known gaps

- Q2's acceptance criterion says the rules must pass on **published reference
  designs**. They pass on the two this project generates, which is the
  strongest check available offline; obtaining published designs to lint is
  outstanding.
- `self_structure` is declared and reported as not checked. It needs a
  thermodynamics backend (the `thermo` extra).

## alpibrupa/nanoindent

A mature AFM package already in the owner's hands, and it changes two things.

**Instrument file readers: half true, and the half matters.** This section
used to say `dynamo_v0/pyfmreader` solved M4's file formats. Reading the code
shows it does not, and the correction is worth keeping rather than quietly
editing away.

`loadJPKimg` accepts `jpk-force-map` and `jpk-qi-data` and returns None for
anything else; `loadNANOSCimg` reads force-volume image offsets out of a
Nanoscope header. Both extract the topography recorded *alongside a force
volume*. Neither reads a plain tapping-mode topography scan, which is what an
AFM group imaging origami on mica actually produces. That repository also
ships no sample files, so a parser written against those formats here could
not have been tested against anything.

What M4 does instead: **Gwyddion reads every native AFM format and exports
Gwyddion Simple Field**, so one fully specified reader covers every instrument
a partner might own, and can be tested exactly by writing files and reading
them back. Native force maps still go through pyfmreader when it is installed,
because that path does work. See `dobladillo/imaging/readers.py`.

**C0 is much closer than this roadmap assumes.** Interface rupture forces by
force spectroscopy is a Tier-3 item here; nanoindent already carries the whole
stack -- Hertz, DMT, Ting, Sader calibration, breakthrough detection, force
maps, viscoelastic fits.

Two cautions, both from the package's own words or code:

- The **live instrument adapters** (`adapters/jpk.py`, `asylum.py`,
  `nanosurf.py`) declare themselves scaffolds: "reconstructed from
  documentation and must be verified against the actual SDK and instrument".
  Reading files is not the same as driving an instrument.
- `pyfmreader` imports `audioop`, **removed from Python 3.13**. It is an unused
  import in at least `loadjpkimg.py`, so deleting the line is the whole fix,
  but it will stop those modules importing the day either project moves past
  3.12. This venv is 3.12, so nothing is broken yet.

What does NOT overlap is the work here: nanoindent is force curves and
indentation mechanics, not segmenting a topography image into particles and
classifying their shapes.

### What has been adapted

`dobladillo.mechanics` (one module, no mechanics in it) supplies the piece
nanoindent cannot know — the thickness a given design folds into — and hands
the plate over. It reports thickness, the thin-film parameter and the regime
with nothing installed, because those are geometry; forces and correction
factors need nanoindent, and say so.

It produced epic #3's experiment and one result that was not expected: a Hertz
fit on a single-layer origami plate on mica reads **5.06x** the true modulus,
the error is exactly independent of that modulus, and no plate thick enough to
escape it is worth folding. `docs/PLATE_INDENTATION.md`.

`docs/methodology_msnl_bio_dc.md` over there is a journal-style methods section
for the same simulation on a 6.2 nm film. It is close enough to a three-layer
plate to serve as the draft of ours with the geometry changed, and its
reference list is the one this work should cite.

`tests/test_mechanics.py` skips its six solver tests when nanoindent is absent,
which is every CI run. The pinned factors in `MEASURED_FACTORS` are what stops
that being silent: run the suite anywhere nanoindent is importable and a
drifted pin fails.

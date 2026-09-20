# Status

Mirrors the table in DESIGN.md section 11. One row per roadmap item.

| Item | State | Notes |
|---|---|---|
| Q1 project skeleton + scadnano round trip | done | both parts build, export to cadnano v2 and round-trip; accounting exact; counts pinned |
| Q2 design-rule validator | done | six rules, each with a seeded failing design; `dobladilo lint`. Caught a real defect in the rectangle. `self_structure` declared unimplemented, not silently passing |
| Q3 lab outputs | done | IDT bulk CSV and plate xlsx, both validated; pooling map, pipetting sheet, protocol with Mg screen; cost estimate with assumptions |
| Q4 oxDNA job bundle | done | all four stages run to completion on CPU in test mode, zero errors. The GPU production run remains the human gate |
| Q5 baseline analysis | done (pending a real trajectory) | parser, dimensions, RMSF, planarity, bend, oxView overlay; `dobladilo analyse`. A long CPU run is under way to give it something that counts as a result |
| M1 Brick and Port abstractions | todo | |
| M2 interface library v1 + orthogonality | todo | |
| M3 assembly composition + stage planning | todo | |
| M4 AFM pipeline | measurement done, readers pending | flatten, segment, measure, classify, yield with a Wilson interval; validated to <1% against synthetic ground truth. Native file readers should come from `alpibrupa/nanoindent`, not be rewritten |
| M5 compare report + first closed loop | todo | first real milestone |
| M6 one-DOF mechanism | todo | |
| C0-C6 | not started | research-grade |

Priority per DESIGN.md section 9: **Q1 through Q5 plus M4**, because those are
what make a first closed loop possible. Everything else waits.

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
  first whose prediction is a distribution rather than a shape.
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

## Known gaps

- Q2's acceptance criterion says the rules must pass on **published reference
  designs**. They pass on the two this project generates, which is the
  strongest check available offline; obtaining published designs to lint is
  outstanding.
- `self_structure` is declared and reported as not checked. It needs a
  thermodynamics backend (the `thermo` extra).

## alpibrupa/nanoindent

A mature AFM package already in the owner's hands, and it changes two things.

**Do not write instrument file readers.** `dynamo_v0/pyfmreader` contains JPK
and Nanoscope **image** loaders that are a byte-for-byte vendored snapshot of
PyFM_YF_version, verified against the originals with `cmp`, and which produced
published result tables. M4's "read native instrument formats" is solved there.

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

`dobladilo.mechanics` (one module, no mechanics in it) supplies the piece
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

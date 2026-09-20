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
| M4 AFM pipeline | todo | standalone module; the piece offered to the partner lab |
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

## Known gaps

- Q2's acceptance criterion says the rules must pass on **published reference
  designs**. They pass on the two this project generates, which is the
  strongest check available offline; obtaining published designs to lint is
  outstanding.
- `self_structure` is declared and reported as not checked. It needs a
  thermodynamics backend (the `thermo` extra).

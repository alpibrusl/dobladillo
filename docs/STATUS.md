# Status

Mirrors the table in DESIGN.md section 11. One row per roadmap item.

| Item | State | Notes |
|---|---|---|
| Q1 project skeleton + scadnano round trip | done | both parts build, export to cadnano v2 and round-trip; accounting exact; counts pinned |
| Q2 design-rule validator | done | six rules, each with a seeded failing design; `dobladilo lint`. Caught a real defect in the rectangle. `self_structure` declared unimplemented, not silently passing |
| Q3 lab outputs | next | scadnano already exports IDT bulk and plate formats |
| Q4 oxDNA job bundle | todo | carries a human gate: GPU run |
| Q5 baseline analysis | todo | needs Q4's trajectories |
| M1 Brick and Port abstractions | todo | |
| M2 interface library v1 + orthogonality | todo | |
| M3 assembly composition + stage planning | todo | |
| M4 AFM pipeline | todo | standalone module; the piece offered to the partner lab |
| M5 compare report + first closed loop | todo | first real milestone |
| M6 one-DOF mechanism | todo | |
| C0-C6 | not started | research-grade |

Priority per DESIGN.md section 9: **Q1 through Q5 plus M4**, because those are
what make a first closed loop possible. Everything else waits.

## Known gaps

- Q2's acceptance criterion says the rules must pass on **published reference
  designs**. They pass on the two this project generates, which is the
  strongest check available offline; obtaining published designs to lint is
  outstanding.
- `self_structure` is declared and reported as not checked. It needs a
  thermodynamics backend (the `thermo` extra).

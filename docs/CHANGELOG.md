# Changelog

## Unreleased

- Project skeleton: package layout per DESIGN.md section 6, `pyproject.toml`,
  ruff/pytest/mypy, CI.
- `constants.py`: geometry, lattice periodicity, scaffold lengths, staple
  rules, wet-lab defaults and the oxDNA salt proxy, each with its source.
- `units.py`: the single place an oxDNA length unit is converted.
- Tests pin the relationships between constants, not just their values.
- Design document transcribed as `docs/DESIGN.md`. Its collaborator section is
  omitted: that is strategy and personal information. Published work stays
  cited normally, including papers by people named there.
- Q1 complete. `_scadnano.py` adapter; `parts.rectangle` (square lattice,
  twist-corrected) and `parts.bundle` (honeycomb six-helix ring); design
  scripts; exports to scadnano, cadnano v2 and oxView.
- CLI with a `--json` mode and a `describe` command, so an agent can discover
  and call it without scraping `--help`.
- Q2 complete. Six composable design-rule checks with structured findings,
  `dobladillo lint` and `dobladillo rules`. Running them found a real defect in
  the rectangle, now fixed.
- Q3 complete. IDT bulk CSV and plate spreadsheet, both validated rather than
  assumed; pooling map; pipetting sheet; folding protocol with the magnesium
  screen; cost estimate that carries its assumptions. `dobladillo lab order`
  and `dobladillo lab protocol`.
- Q4. Self-contained oxDNA job bundles: topology, configuration, mutual traps,
  an input file per relaxation stage, a run script and metadata.
  `dobladillo sim bundle`. The relaxation follows oxDNA's own documented
  procedure, which differs from DESIGN.md section 3 in its first stage; the
  difference is recorded in every bundle's metadata.
- Q5. Trajectory parsing without oxDNA, dimensions by principal axes, RMSF with
  superimposition, planarity, axis bend, and an oxView overlay.
  `dobladillo analyse`, plus `dobladillo sim check`, which refuses to let a
  smoke-test trajectory be analysed as a result.

### 2026-09-28 — rebuild on mature tools (epic #21)

- Licence changed to EUPL-1.2. `tests/test_licences.py` fails on any
  dependency whose licence has not been reviewed, on an incompatible licence,
  and on any network import in the package.
- `routing.azimuth` and the `crossover_azimuth` rule replace
  `crossover_phase`. The rule separates phasing strain from twist and is
  calibrated on five published designs (`tests/data/reference_designs`).
  (#6)
- Every square part was half misphased and has been re-tiled. The rectangle
  and twist pair are built on scadnano's `origami_rectangle`; the hinge is
  tiled by 16-bp column. E1 and E2 orders were regenerated before anything
  was ordered.
- The six-helix bundle now tiles scadnano's published 6HB unit, at 17° rms
  (it was 44°).
- `dobladillo predict`: a CanDo-class beam shape predictor. It cannot see
  phase, and says so. (#22)
- Runs and queues default to `$DOBLADILLO_RUNS`, and the tools warn when a
  path is under a temp directory. (#16)
- `sim bundle` refuses designs whose sequences do not pair.
  `assign_scaffold_sequence` can be called again after a design change.
- Added `dobladillo experiment compare-arms`, E2's blinded two-arm
  comparison. It reads tip radii and the reference height from the
  experiment record and states the verdict under both unblindings. (#18)
- Added `Measured`/`Nominal` reading types and a single reader for
  `during/instrument.json`. `deconvolve_tip` now requires a `Measured` tip
  radius and no longer defaults to 10 nm. `experiment new`'s instrument
  template gains `measured_radius_between_nm`, `imaging_order` and
  `reference`. (#12)
- MCP server (`dobladillo mcp`, optional `mcp` extra): typed tools over
  parts, rules, the oxDNA queue and experiments, compare-arms included.
  They wrap the CLI's --json output, so refusals keep their `kind`. No tool
  passes a human gate. (#11)
- Provenance chain (#13). Every artefact records its parent by content hash:
  design → prediction → simulation → order → experiment → scan →
  comparison. `experiment report` refuses `design_mismatch` and
  `provenance_incomplete`. Legacy folders (E1, E2) are reported as having
  no design hash recorded.
- Local export archive in a documented Nanobase-shaped layout, with
  `dobladillo export` and `export-check`. Nothing is ever uploaded. (#19)
- AFM native formats are read directly through AFMReader (GPL-3.0,
  `imaging` extra): Bruker, JPK, Asylum, Gwyddion and WSXM. Three things are
  refused, each with its reason:
  - WSXM `.top`: AFMReader truncates the Z amplitude;
  - truncated Bruker files: pySPM hangs on them;
  - high-speed stacks.
  `experiment report` and `compare-arms` read native files and never their
  `.gsf` copies. (#7)
- TopoStats rejected for now: it hard-requires topoly (binary-only, with a
  contradictory licence), TensorFlow and Python < 3.12. The built-in flatten
  and segmentation stay. (#8)
- Thermodynamics through primer3 (#10). primer3-py is now a core
  dependency. The SantaLucia 1998 table is kept as test reference data.
  Non-ACGT input and duplexes over 60 bp are refused. The ladder shifts by
  a uniform −0.025 kT, because primer3 uses the 2004 initiation entropy.
- Analysis through oxDNA_analysis_tools (#9): alignment, mean structure and
  RMSF. It is pinned to oxDNA v3.7.0 and installed from git (GPL-3.0), via
  the `analysis/_oat.py` adapter. The adapter never writes next to a
  trajectory, never prints to stdout and picks a fixed reference frame.
  Every reported number matches the old implementation on the 200-frame
  bundle run.
- `dobladillo benchmark` (#14): known answers for routing and shape
  prediction, each sourced (`tests/data/known_answers.json`), including
  negative controls, strict known failures and wanted-but-missing entries.
  Adds Dietz 2009's 120° design.
- Synthetic twins (#15). A FRET twin generates bursts and bulk plates with
  known p(latched) and known calibration, alongside an estimator with a
  γ self-check. `experiments/protocols/e4_dryrun.py` runs E4 end to end
  on synthetic data. A beam-predictor twin (`mechanics/twin.py`) provides
  designs with textbook answers.
- Removed `experiments/protocols/e2_compare.py`. (#18)
- Staple rules relaxed to the published evidence (maintainer's decision):
  - staple length hard floor 16 nt;
  - `seed_domain` is now a warning;
  - `min_domain` is hard below 2 nt and warns below 5;
  - `crossover_azimuth` judges placement and warns on designed strain.
  Crossovers into single-stranded DNA are unscored.
- E4 gains locked-open and locked-latched FRET references. Hinges can carry
  several latches (`extra_latches`); `bracket` reports both references;
  `lab order hinge-locked-open` and `lab order hinge-locked-latched`.
- E1 and E2 were re-scaffolded into `experiments/2026-09-28-*` with the
  provenance chain; the old folders are marked SUPERSEDED. E1 gains a
  positive-control arm. `experiment check` flags an unwritten gate.
- E10, the six-helix bundle's 3D fold:
  - `experiment rods` traces rods;
  - `imaging.wlc` gives the wormlike-chain prediction and separates thermal
    bending from a built-in arc;
  - synthetic rod scans;
  - `lab.published` holds the folding protocol, taken whole from Enlund
    et al. 2024, with unstated parameters left to the lab;
  - `experiment new --part bundle` predicts an 8 nm height, not 2.
- E8, the patterned rectangle: 28 of E1's staples carry a hairpin that
  draws a chiral F on one face (the face was measured from scadnano's 3D
  export). Only those 28 are ordered, and `lab order` says which E1 wells to
  leave out of the pool. Also `imaging.pattern`, synthetic patterned scans,
  `experiment pattern`, and a dry run. `find_particles` gains
  `peak_percentile`.
- E9, rectangle dimer:
  - components A and B each reuse 198 of E1's 220 staples, and pair through
    eleven 12-nt sticky ends chosen with primer3; 12 is the shortest length
    that passes all four checks;
  - every helix end on every edge carries a 4-T tail;
  - `imaging.assembly` counts monomer, dimer and larger particles, with the
    A-alone and B-alone controls and a replicate homogeneity test;
  - `experiment assembly`, `lab order dimer` (44 extra oligos, not 440),
    a protocol and a dry run.
- Two defects found while building E9. Mutually complementary sticky ends
  (a designed self-dimeriser) were accepted; they are now refused. And
  `find_particles` was losing tall aggregates, which became frame-sized
  "particles" and were excluded. With that fixed, `afm measure` and
  `experiment report` average dimensions over well-formed particles only.
- Folding window (`sequence.folding`, `dobladillo folding-window`): each
  staple's melting temperature against the scaffold in the folding buffer
  (primer3, staple in excess), the 10-90% window, the weak staples, and a
  suggested isothermal screen. It is recorded in every new experiment's
  prediction.json.
- E11, isothermal folding screen: a protocol (gradient block, 12
  temperatures × 3 times, normalised to E1's ramp fold on each gel) and
  `experiment folding-screen`, which reads the Fiji quantification and reports
  the fastest good fold beside the predicted window.
- Roadmap: high-speed AFM recorded as a direction: hinge switching first,
  folding second.
- Project: an open DNA-origami calibration kit and method for AFM
  (`projects/afm-calibration-kit/`: `PROJECT.md`, `MATERIALS.md`), planned
  2026-09-29 after a literature review. Protocols K1-K8 in
  `experiments/protocols/` (software validation, the calibration tile's fold,
  lateral calibration against a traceable grating, tip reconstruction against
  the GATTA-AFM 3D staircase, preparation sensitivity, HS-AFM scale, drift and
  marker survival, kit format and shelf life, certification). Every gate is left
  empty, with a proposal. Indexed in `experiments/protocols/README.md` and
  `experiments/ROADMAP.md`; not yet in `programme.py`.
- `dobladillo/calibration/` and `dobladillo calibrate`: AFM calibration from
  reference particles, each value with an uncertainty and a list of what that
  uncertainty leaves out. `calibrate reference` writes the calibration tile's
  nominal geometry; `calibrate lateral` fits the scanner's x/y scale and skew
  together with the tile's own anisotropy from mark centroids (tip-insensitive:
  5 vs 15 nm tips moved centroids 0.11 nm rms), refusing when landing angles
  cannot separate the two; `calibrate tip` is Villarrubia's blind tip
  reconstruction implemented from the 1997 paper (an outer bound; flags a scan
  that cannot constrain the tip), with apex radius and the lateral resolution
  it allows; `calibrate drift` measures drift between frames by sub-pixel
  cross-correlation. Validated on synthetic scans with known truth, including
  interval coverage (bootstrap reads ~15% low, stated). MCP tools
  `calibrate_reference|lateral|tip|drift`, bounded to the experiments root.
  Not built: a folder-level `calibrate report`; HS-AFM movie formats; grating
  pitch analysis (use Gwyddion).
- Part `calibration-tile`: E1's rectangle with 12 isolated, chiral hairpin
  cells (48 marker staples), the ruler for `calibrate lateral`.
- README facts generated from the code (`dobladillo readme`, module
  `dobladillo.readme`): every command with its usage from its declared
  arguments, the install extras from `pyproject.toml`, the MCP tools from the
  running server, and the commands no tool may wrap. Prose outside the
  `<!-- generated:NAME -->` markers stays hand-written. `tests/test_readme.py`
  fails on drift, and checks the README's install line is the one CI runs.
- Biotin marks (#32): `patterned_rectangle(marker="biotin")` and
  `calibration_tile(marker="biotin")` put a TT spacer and a 3' biotin (IDT
  `/3Bio/`, scadnano's own) on the same staple ends the hairpins use, so the
  ruler is identical. Part `calibration-tile-biotin` orders K6's streptavidin
  arm. Order validators accept the IDT codes of scadnano's built-in
  modifications and reject any other; the cost estimate states that it
  excludes the vendor's modification surcharge.
- Pixel noise from second differences (#31): cancels line offsets and feature
  slopes, so a crowded scan no longer reads 8x noisier than it is (0.42 ->
  0.06 nm for a true 0.05) and `calibrate tip` stays informative on it.
- Lateral fit uncertainty measured (#30): over 200 synthetic sessions the
  bootstrap u is honest (errors 0.98-1.07 u) with particles spread over 4
  images; with 2 images scale_x reads ~18% low, because errors shared within
  an image are invisible to a bootstrap over particles. The earlier "~15% low"
  came from 30 sessions, too few to tell. Results now carry `n_images` and a
  warning below `MIN_IMAGES_FOR_HONEST_U` = 4.

# Project: an open DNA-origami calibration kit and method for AFM

**Status:** planned 2026-09-29, after a literature review. No sample exists. The
software (`dobladillo calibrate reference|lateral|tip|drift`, package
`dobladillo/calibration/`) and the part (`calibration-tile`) exist since
2026-09-29 and are validated on synthetic scans only.
**Experiments:** K1–K8, protocols in
[`experiments/protocols/`](../../experiments/protocols/README.md#the-afm-calibration-kit-k-series).
**Materials:** [`MATERIALS.md`](MATERIALS.md).
**Builds on:** E1 (the rectangle), E8 (hairpin marks), E10 (six-helix bundle),
E11 (isothermal folding).

Every success criterion below is a **proposal**. Agents never write gates
(`experiments/AGENTS.md`); the maintainer and the experimentalist decide them,
per experiment, in `pre/plan.md`, before the session.

---

## Goal

An AFM image is only as good as three things nobody sees in it: the scanner's
lateral scale (X, Y, and the angle between them), the tip's shape, and how the
sample moved while it was scanned. Every dimension in this project's
experiments goes through all three, and so does every dimension anyone else
reports from an AFM.

The goal is a **calibration kit** that anyone can make, check and improve,
consisting of four parts that are only useful together:

| part | what it is | who can use it |
|---|---|---|
| **samples** | the calibration tile (an all-DNA patterned rectangle) and the six-helix bundle (6HB), folded from published open designs | anyone who can fold origami, or buy the oligos |
| **protocol** | how to fold, purify, store, deposit and image them (K2–K7) | the bench |
| **software** | `dobladillo calibrate`: scale X/Y, skew, tip, resolution and drift, each with an uncertainty, read from **any** reference whose geometry is declared | anyone with an AFM image of a declared reference, ours or not |
| **certificate method** | how a value and its uncertainty are assigned to a batch of tiles against a traceable reference (K8) | a partner with a traceable instrument; the maintainer decides |

The deliverable is all four, open: designs and software under this repository's
licence (EUPL-1.2), protocols as written here, and the certificate method as a
procedure anyone can repeat.

## What the kit is made of

**The calibration tile** (`calibration-tile`) is E8's
patterned rectangle with a different pattern. E8 is E1's rectangle with a
hairpin on the 3′ end of selected staples; the hairpins stand above the sheet
and a marked **cell** (32 bp × 4 helices, about 10.5 × 12 nm at design values,
four staple ends) shows as a raised spot. E8 draws an F with them. The tile
instead marks a **sparse, chiral pattern of isolated cells**, and the
**centres of those cells are the ruler**:

- *isolated* — no two marked cells touch, so each shows as its own spot and
  its centre can be located. A working 10 nm tip draws a 2 nm mark about 6 nm
  in radius (`parts/pattern.py`), so neighbouring cells merge;
- *chiral and off-centre* — as E8's F, so a particle's handedness and
  orientation are known and each spot can be matched to its designed cell
  (the part refuses a pattern whose turned and mirrored copies differ in
  fewer than 3 cells);
- *spread over the usable grid* — the grid is 10 × 5 cells, and the first and
  last columns cannot be marked (their staple ends lie in the plane). At
  design values the longest centre-to-centre spans available are about 73 nm
  along the helices and 48 nm across them.

Which cells are marked is the part's decision, pinned in its tests, not this
document's.

**Why centres.** The tip widens a spot evenly on all sides, so it moves the
spot's edge but, to first order, not its centre. A distance between two
centres is therefore much less sensitive to the tip radius than an edge
length is. That is the difference from E1, where the tip correction removes a
quarter of a width. A tip that is not symmetric does shift centres, which is
one reason K4 reconstructs the tip anyway.

**The six-helix bundle** is E10's `bundle`: a rod of 390.4 nm contour and 8 nm
diameter. It is the long-range length reference (five times the tile's span)
and a taller object for the tip (K4). It is only in the kit if E10 finds it
straight.

### What the tile can and cannot calibrate before it is certified

This decides the scope, so it comes before the non-goals.

- **Along the helices** the designed pitch is known to about 2.4%: scadnano's
  0.332 nm per base pair against the literature's 0.34 (`constants.py`,
  `RISE_PER_BP_NM`, which pins the gap).
- **Across the helices** it is not known from the design at all. The part
  places helices 3.0 nm apart (scadnano's geometry, which gives E1's predicted
  66.0 nm), while `constants.py` records an effective spacing of 2.25–2.6 nm
  that depends on magnesium. That is a 13–25% disagreement inside this
  repository, before any preparation effect.
- **Anisotropy and skew** do not need the absolute value. Particles land at
  random angles. A scanner's X/Y scale difference and its skew stay fixed in
  the image frame, while the tile's own shape turns with the particle. Many
  particles at many angles therefore separate the instrument's distortion
  from the object's shape. What stays tied together is one overall scale
  factor, which the object and the instrument share. Whether `calibrate
  lateral` uses this is up to its implementers. If it does, K1 tests it.

So, **uncertified**, the tile gives X/Y ratio and skew, plus the along-helix
scale to within the design uncertainty and the preparation spread (K5). The
across-helix scale, and any absolute scale with a traceable uncertainty, come
only from K8.

## Scope

In scope:

- lateral scale X and Y, and skew, at scan sizes of about 0.5–2 µm (where the
  tile is resolved), with uncertainty;
- a comparison of that against a traceable grating at a larger scan size (K3);
- tip shape by blind reconstruction, and tip wear over a session (K4);
- resolution, as the smallest mark separation read correctly, and drift, from
  mark positions over time (K3, K6);
- high-speed AFM in liquid, which is what an all-DNA reference is best placed
  for (K6);
- preparation sensitivity, which becomes the uncertainty (K5), and kit format
  and shelf life (K7);
- a method for certifying a batch against a traceable reference (K8).

### Explicit non-goals

- **No absolute Z standard.** DNA heights depend on imaging force, drying and
  buffer: E1 expects 1–1.5 nm dry for a 2 nm sheet, and nobody here has
  measured how tall the hairpins stand. Heights are reported, never
  certified. For Z, use a certified step-height standard. Mechanical
  calibration of Z-dependent quantities is E7's line (`docs/COMMERCIAL.md`
  §1), not this project's.
- **Not SI-traceable until certified.** Until K8 has run, nothing from this
  kit may be described as traceable, a standard, or certified, and every
  value it produces carries the design value's uncertainty and K5's spread.
  The software says which it used.
- **Not competing with GATTAquant.** `calibrate` reads their samples as well
  as ours: any reference whose geometry is declared. Their samples are this
  project's comparators (K4, K5), bought as purchases. The open contribution
  is the software, the all-DNA design for liquid and HS-AFM, and the
  certificate method, not a cheaper copy of a product.
- **Not a fluorescence ruler.** DNA-PAINT nanorulers exist and are traceable
  (Raab et al. 2018); this kit is for AFM.
- **No contact with anyone.** Partners are listed below as a decision for the
  maintainer (`AGENTS.md`, standing prohibitions).

## Prior art

Read 2026-09-29. GATTAquant prices are as listed on that date.

| what | who | what it provides | what it does not |
|---|---|---|---|
| **GATTA-AFM** | GATTAquant (commercial), EUR 350 | a DNA-origami rectangle of about 90 × 70 nm with a 6 nm line ladder | no certified values |
| **GATTA-AFM 3D** | GATTAquant (commercial), EUR 450; published as Kolbeck et al., *Nano Lett.* 23, 1236 (2023), doi:10.1021/acs.nanolett.2c04299 | a 4-step staircase of about 2.5 / 5 / 12.5 / 20 nm for blind tip reconstruction | no certified values |
| **Seeman tile as an AFM xyz standard** | Korpelainen et al. (VTT MIKES), *Meas. Sci. Technol.* 28, 034001 (2017), doi:10.1088/1361-6501/28/3/034001 | height 2.0 ± 0.2 nm, width 88 ± 3 nm; dry samples stable for at least 12 months | not a liquid or HS-AFM reference; no open software |
| **SI-traceable origami distances** | Raab et al. (PTB), *Sci. Rep.* 8, 1780 (2018), doi:10.1038/s41598-018-19905-x | traceable distances on origami | measured by DNA-PAINT, not AFM |
| **HS-AFM tip invasiveness with origami** | Kielar et al., *Angew. Chem.* (2020), doi:10.1002/anie.202005884 | tip invasiveness measured with origami | shows streptavidin markers stripped by the tip, which is why the tile's marks are all-DNA (K6 tests it) |
| **Preparation-dependent dimensions** | reported in the literature reviewed | a 3–10% spread in origami dimensions depending on preparation | the size of the problem K5 measures for our tile |
| **Blind tip reconstruction** | Villarrubia, *J. Res. Natl. Inst. Stand. Technol.* 102, 425 (1997) **[literature — check the citation before quoting it]** | the algorithm `calibrate tip` implements; the estimate is an outer bound on the true tip | characterises the tip only to the depth of the tallest feature imaged |
| **Public AFM data of origami** | Rabbe & Keller (2025), Zenodo record 15370091 | streptavidin-decorated origami AFM images, usable for K1 | **licence not yet checked**; must be before use |

## Phases and experiments

| phase | experiment | question | lab? |
|---|---|---|---|
| 0 — software | [**K1**](../../experiments/protocols/K1-software-validation.md) | does `calibrate` recover known scale, skew, tip and drift, with honest uncertainties? | no |
| 1 — the tile exists | [**K2**](../../experiments/protocols/K2-calibration-tile-fold.md) | does the tile fold, purify and show its marks, and how much do we get? | yes |
| 2 — one instrument | [**K3**](../../experiments/protocols/K3-lateral-calibration.md) | does the tile calibrate X, Y and skew in air and liquid, and agree with a traceable grating? | yes |
| | [**K4**](../../experiments/protocols/K4-tip-reconstruction.md) | do the tile and the 6HB reconstruct the same tip as the GATTA-AFM 3D staircase, and how fast does it wear? | yes |
| 3 — how good a reference | [**K5**](../../experiments/protocols/K5-preparation-sensitivity.md) | how much do the tile's dimensions move with preparation? That spread is the uncertainty | yes |
| | [**K6**](../../experiments/protocols/K6-hsafm-scale-drift-markers.md) | HS-AFM in liquid: scale, drift, and do all-DNA marks outlast streptavidin under the tip? | HS-AFM |
| 4 — a kit | [**K7**](../../experiments/protocols/K7-kit-format-shelf-life.md) | which format survives: frozen aliquots, freeze-thaw, dried on mica; for how long? | yes, 12 months |
| 5 — certified | [**K8**](../../experiments/protocols/K8-certification.md) | a value with a traceable uncertainty for one batch | partner lab; the maintainer decides |

### Dependencies

```
E1 ── E8 ──┐                      the tile needs E1's fold and E8's visible marks
E11 ·······┤                      (optional: the isothermal arm of K2)
           K2 ──┬── K3 ──┬── K5 ── K7 ── K8     the reference line
K1 ─────────────┤        └── K6                 HS-AFM (needs an instrument)
E10 ────────────┴── K4                          tip: tile + 6HB against the staircase
    ·············· K3                           (the 6HB arm of K3, if E10 passed)
```

- **K1** needs only the software. It gates every readout from K2 on: a real
  image is never the first thing `calibrate` sees.
- **K2** needs E1 (its magnesium, a fold, its staple plates) and E8 (marks
  visible at all: the E8 dry run needs them about 1 nm above the sheet). E11
  is optional and only for the isothermal arm.
- **K3** needs K1 and K2. The 6HB arm needs E10 to have passed.
- **K4** needs K1, K2 and E10; without E10 it runs with the tile alone
  against the staircase.
- **K5** needs K3 (a fixed measurement procedure: variation must come from the
  preparation, not the method).
- **K6** needs K3's liquid arm, an HS-AFM, and a reader for HS-AFM stacks
  (the current pipeline refuses `.asd`; see *Open* below).
- **K7** needs K3 (a baseline) and K5 (the spread, which says what change is
  detectable).
- **K8** needs K5 and K7 (what is certified is a preparation and a format,
  not a molecule), and a partner. It is the maintainer's decision whether it
  happens at all.

## Success criteria — proposals for the maintainer to write

Not gates. Each is a starting point for the per-experiment gate in
`pre/plan.md`, which the experimentalist writes.

**Phase 0 (K1).**
- On synthetic images with injected scale, skew, tip and drift, recovered
  values within their stated uncertainty in at least 95% of seeds per
  condition (coverage), and within 1% of truth on scale at the reference
  imaging settings (accuracy).
- Refuses, rather than returns a number, when the reference is undeclared,
  too few marks are found, or the pixel is too coarse.
- Tip reconstruction agrees with Gwyddion's blind estimation on the same
  images, within the stated uncertainty.

**Phase 1 (K2).**
- A folded band comparable to E1's in the same gel; at least 100 well-formed
  tile particles read in detail scans; on face-up particles, at least 70% of
  designed marked cells found and few marks where none was designed. Below
  half, the tile cannot carry a ruler as designed.

**Phase 2 (K3, K4).**
- X/Y ratio and skew from the tile agree with the grating's within their
  combined uncertainty (they are instrument properties and must not depend on
  the artefact).
- The tile's along-helix scale agrees with the grating's within the design
  uncertainty (2.4%) plus K3's own.
- In the height range the tile probes, its reconstructed tip agrees with the
  staircase's within uncertainty; tip wear is resolved between the first and
  last reconstruction of a session, or bounded.

**Phase 3 (K5, K6).**
- The dimension spread across the preparation matrix is stated with its
  interval. **What spread is acceptable for a calibration reference is the
  maintainer's call**; the literature's 3–10% is the range to beat.
- In HS-AFM, hairpin marks survive longer than streptavidin markers under the
  same imaging, or the difference is bounded.

**Phase 4 (K7).** At least one format keeps yield, mark detection and scale
within K5's spread over 6 months (12 for the dry format, as Korpelainen et al.
report for theirs).

**Phase 5 (K8).** A value and uncertainty for one batch from a traceable
measurement, with a complete uncertainty budget. Whether to call anything
"certified" is decided after this, not before.

## Risks

| risk | what it would do | where it is found | what we can do |
|---|---|---|---|
| hairpin marks not visible in liquid, or pressed flat | no ruler | E8, K2, K3 | lower force; sharper tip; a taller mark is a new design |
| marks visible on about half the particles only (face-down) | halves the useful count | E8, K2 | expected; count targets allow for it |
| preparation spread above what a reference tolerates | the uncertainty swamps the use | K5 | declare one preparation tightly and certify that only |
| sheet deforms non-affinely on mica | the ruler is not rigid; skew from the sample, not the scanner | K3, K5 | the rotation averaging in K3 exposes it; report, do not fit it away |
| across-helix spacing unknown | no across-helix scale without K8 | already known | use along-helix, anisotropy and skew until certified |
| blind reconstruction limited to 2–3 nm depth on the tile | cannot characterise the tip's sides | K4 | the 6HB and the staircase reach higher; say which depth each covers |
| HS-AFM access; stacks unreadable today | K6 cannot run | K6 | the maintainer's decision; reader in `calibrate drift` |
| streptavidin comparator needs a biotin variant the toolchain cannot order | K6 arm B cannot run | K6 | design decision; K6 arm A runs alone |
| public data licence forbids use | K1 loses its real-data arm | K1 | synthetic data and our own K2/K3 images |
| no partner for traceable measurement | no certificate | K8 | the kit stays an uncertified, open reference, and says so |
| HS-AFM movie formats unread | K6 needs exported frames | K6 | export frames as .gsf from Gwyddion |

## What partners would be asked for

A list for the maintainer to decide on. Nobody is contacted by this project,
and no outreach is drafted.

1. **Traceable lateral measurement of the tile** (K8), on an instrument with
   an SI-traceable position measurement, and its uncertainty budget.
2. **A second and third AFM** for the same K3 protocol, as an inter-lab
   comparison: raw native files, `instrument.json`, and the tip before and
   after.
3. **HS-AFM time in liquid** for K6, and the operator's validated imaging
   buffer and cantilever.
4. **An independent reading** of the same images with the partner's own
   software, so that a disagreement can be located before it is attributed to
   the sample.
5. **Their samples' declared geometry**, if a supplier or group is willing to
   state it, so `calibrate` reads them without guessing.

## Open

- `calibration-tile` and `dobladillo calibrate reference|lateral|tip|drift`
  exist (2026-09-29), and `calibrate report` runs them over a K folder: it
  finds the scans in `during/raw/` by name (`pattern-`/`overlap-`, K4's
  `S1-01` blocks, `frame-`), takes the conditions from `instrument.json`, and
  writes `post/calibration.json`. Not built: summaries across codes, time
  points or partners (K5, K7, K8). The commands' own `--help` wins over any
  argument shown in a protocol.
- The current pipeline refuses HS-AFM stacks (`.asd`, `.h5-jpk`;
  `imaging/readers.py`). K6 needs `calibrate drift` to read them.
- `during/instrument.json` records the deposition cations (MgCl₂, NiCl₂),
  scan angle, trace/retrace and closed loop since 2026-09-29, and
  `experiment check` asks for them in calibration-tile folders. K5's
  per-code key stays in `during/conditions.csv`, which nothing reads yet.
- The K series is not yet in `dobladillo/programme.py`, so the dashboard does
  not show it. Scoring it (relevance, difficulty, P(success)) is a judgement
  for the maintainer.

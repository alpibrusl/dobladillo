# K3 — Lateral calibration on one instrument: does the tile agree with a traceable grating?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 2
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k3-lateral/`, and,
for the optional bundle arm, `experiments/<YYYY-MM-DD>-k3-bundle/`
**Run after:** K1 (software validated for these scan settings) and K2 (the tile
folds, its marks are found, aliquots exist). The bundle arm also needs E10 to
have passed
**Time:** two AFM days (liquid, then air) plus half a day of analysis
**Cost:** no new oligos. A traceable grating if the lab has none (MATERIALS §6)
**Read first:** [`common-techniques.md`](common-techniques.md) §7–§11, [K2](K2-calibration-tile-fold.md),
[PROJECT.md](../../projects/afm-calibration-kit/PROJECT.md) (*What the tile can
and cannot calibrate*). Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md)

---

## What you are testing, and why it matters

An AFM's lateral scale is usually calibrated on a grating: a surface with
lines or pits at a pitch known from a certificate. That works well at scan
sizes of several micrometres, where many periods fit in the image. It says
less about the scale at the half-micrometre to two-micrometre sizes where
origami, proteins and most single molecules are imaged. Piezo scanners are
not perfectly linear, so a scale that is right at 10 µm need not be right at
1 µm.

The tile is meant to fill that gap: a ruler of about 10–75 nm spans, imaged
at exactly the sizes where molecules are. K3 is its first real test, on **one
instrument**, in **liquid** (the case the tile is designed for) and in
**air**.

Three things are measured, and they are kept apart:

1. **X/Y ratio and skew.** Properties of the scanner. Particles land at random
   angles, so these come from the tile **without** knowing its absolute size
   (PROJECT.md). They must agree with the grating's, because the scanner does
   not know which sample is under it. If they disagree, either the software
   or the tile is at fault, and the tile's disagreement would be something
   like shear on the mica.
2. **Absolute scale.** Tied to the tile's true size, which is known only to
   the design uncertainty: about 2.4% along the helices, and not at all
   across them (PROJECT.md). K3 measures the tile against the grating. It
   does not certify the tile. That is K8.
3. **Mark detection rate**, in air and in liquid, on this instrument, and the
   smallest mark separation that is read correctly.

## What it decides

- Whether the tile can calibrate X/Y ratio and skew on its own, today,
  uncertified.
- How the tile's along-helix scale compares with the grating's, and whether
  the difference is inside the design uncertainty.
- Whether the scanner's scale changes between the grating's scan size and the
  tile's. The overlap scans measure this.
- Whether air imaging keeps enough marks to be a kit option, or the kit is
  liquid only.

## The comparison, and why there is an overlap scan size

```
grating, large scan (e.g. the size your lab normally calibrates at)  ──┐ scanner
grating, overlap scan (2 µm, 1024 px)                                ──┤ linearity
tile,    overlap scan (2 µm, 1024 px)                                ──┘
tile,    detail scan  (1 µm, 512 px)                                 ──── K2's setting
```

At the **overlap size** the grating and the tile are imaged with the same
settings. Their ratio is then the tile's size relative to the certificate,
with scanner non-linearity removed. Grating large against grating overlap is
the scanner's linearity between the two sizes. Tile overlap against tile
detail is the same check at the small end.

**What the grating must have.** At least about 5 periods in a 2 µm scan, so a
**pitch of 400 nm or less**, and a certificate stating pitch, uncertainty and
traceability. If your grating is coarser, image it at the smallest scan size
with 5 periods and record it. The comparison then assumes the scanner is
linear between that size and 2 µm, and the report must say so.

## What is predicted

| quantity | predicted | note |
|---|---|---|
| X/Y ratio, skew from the tile | equal to the grating's | instrument properties |
| along-helix scale, tile against grating | 1 within about 2.4% | 0.332 vs 0.34 nm/bp (`constants.py`) |
| across-helix scale | **not predicted** | 3.0 nm spacing in the design, 2.25–2.6 nm in `constants.py` |
| mark detection rate | K2's figure, in liquid | air: **not predicted** |
| bundle contour (optional arm) | 390.4 nm | E10's prediction, a long-range check |

## The gate

Copied into `pre/plan.md` and written there by the experimentalist before the
session:

> criterion:

### Proposed, not adopted

> **Count.** Per medium, at least **100** face-up tile particles with at least
> three non-collinear marks found.
> **Scanner properties.** X/Y ratio and skew from the tile agree with the
> grating's at the overlap size within their combined 95% uncertainty.
> **Scale.** The along-helix scale from the tile agrees with the grating's
> within 2.4% plus the combined uncertainty. The across-helix scale is
> reported, not judged.
> **Air.** Informative: the detection rate in air against liquid. If it falls
> below K2's gate on marks, the kit is liquid-only, and that is a result.
> **Fail.** Tile and grating disagree on X/Y ratio or skew beyond their
> uncertainty. Either `calibrate` has a fault K1 did not find, or the tile
> deforms on mica. Both stop K5 until they are understood.

---

## 0. Create the folders

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k3-lateral --part calibration-tile --root experiments
```

(`--part calibration-tile` is being implemented.) **Do not order**: K3 uses
K2's aliquots. For the bundle arm, if E10 passed:

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k3-bundle --part bundle --root experiments
```

The bundle has its own folder so that `experiment rods` can read it, and so
it is never pooled with the tile. Its `during/log.md` names the K3 folder that
holds the session's grating images.

Write the gates and commit both `pre/` folders.

## Checklist before you start

- [ ] K1's validated range covers 1 µm at 512 px and 2 µm at 1024 px.
- [ ] K2's aliquots: at least 4 (two per medium, and spares).
- [ ] The grating, its certificate (pitch, uncertainty, coverage factor,
      traceability, date) copied into `during/log.md`.
- [ ] Liquid and air tips from one lot; tip characteriser.
- [ ] Imaging buffer (MATERIALS §2), one MgCl₂ value, written in `pre/plan.md`.
- [ ] The instrument warmed up as its manual says; the time recorded.
- [ ] Bundle arm: purified bundle from E10's protocol, or a fresh E10 fold.

---

## Day 1 — Liquid (a full AFM day)

### 1. Grating, start of session (45 min)

With the scanner in the configuration you will use all day (closed loop on or
off: record which and keep it), image the grating:

- **large** scan, at the size you chose: 2 images, scan angle 0°;
- **overlap** scan, **2 × 2 µm, 1024 px**: 2 images at 0°, 2 at 90° if your
  instrument rotates the scan.

Save trace and retrace. Files to `during/raw/grating/`, named
`grating-large-01`, `grating-overlap-01`, and so on.

### 2. Tip, before (20 min)

Common-techniques §8, with the **liquid** tip. `tip.measured_radius_before_nm`.

### 3. Deposit the tile (15 min)

Thaw one K2 aliquot on ice, dilute to 1–2 nM in the Mg deposition buffer,
deposit, add imaging buffer (common-techniques §7, liquid). The aliquot is
single-use. Discard what is left.

### 4. Image the tile (3–4 h)

| image | size | pixels | pixel | how many |
|---|---|---|---|---|
| detail | 1 × 1 µm | 512 | ≈ 2.0 nm | until **≥ 100** face-up particles with marks |
| overlap | 2 × 2 µm | 1024 | ≈ 1.95 nm | at least 6, **half at scan angle 0°, half at 90°** |

Gentle setpoint. Separate areas. For each image, save **trace and retrace**,
and take pairs with the slow scan **up and down** where the software allows:
the pair gives drift. Files to `during/raw/liquid/`, named `pattern-01`, …
(detail) and `overlap-01`, … (overlap).

### 5. Tip, after (20 min), and grating, end of session (30 min)

`tip.measured_radius_after_nm`. Then the grating's overlap scans again (2
images). Grating start against end is the scanner's stability over the day.

## Day 2 — Air

Repeat steps 1–5 with a **dry** deposition (common-techniques §7, air) and
the **air** tip. Files to `during/raw/air/`. The `instrument.json` has one tip
record. Put the air tip's radii in the log and in `during/scans.csv`
(below), and say which record is which.

### Bundle arm (either day, 1–2 h)

In the bundle folder: tip before and after (the same tip as the tile, if the
session allows), E10's deposition, **2 × 2 µm at 1024 px** until **≥ 100
rods** (E10, step 11). Files to that folder's `during/raw/`.

---

## What to record

`during/instrument.json` as common-techniques §10, and a table with one row per
image, `during/scans.csv`:

```
file,sample,medium,scan_size_nm,pixels,scan_angle_deg,channel,slow_scan,closed_loop,rate_hz,time,tip
liquid/pattern-01.spm,tile,liquid,1000,512,0,trace,up,on,1.0,10:42,liquid-A
...
```

(the rows show the format only). `instrument.json` has no fields for scan
angle, trace/retrace or closed loop, which is why this file exists. **Its
format is this protocol's proposal. If `calibrate` defines an input format
when it lands, that format wins, and this table is converted. The raw files
are never touched.**

`during/log.md`: the grating certificate; warm-up time; room temperature at
start and end; buffer and MgCl₂; deposition times; anything that drifted,
jumped or streaked.

## Readout

```bash
uv run dobladillo afm read experiments/<folder>/during/raw/liquid/pattern-01.<ext>
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate lateral experiments/<folder>   # (being implemented)
uv run dobladillo calibrate drift experiments/<folder>     # (being implemented)
uv run dobladillo calibrate report experiments/<folder>    # (being implemented)
```

From `calibrate` (being implemented), per medium and scan size: scale X,
scale Y, skew, each with its uncertainty, from the tile and from the grating
(declared with its certificate pitch); the tile/grating ratio at the overlap
size; grating large/overlap; mark detection rate and false-mark rate; the
smallest designed mark separation read correctly; drift from up/down pairs.

Bundle arm, with a command that exists today:

```bash
uv run dobladillo experiment rods experiments/<YYYY-MM-DD>-k3-bundle
```

Tip-corrected contour against 390.4 nm, over 390 nm of rod, five times the
tile's longest span. Fill the bundle folder's `instrument.json` as E10's step
14 asks, including E1's reference height. `experiment rods` refuses without
it and without a measured tip.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| tile and grating disagree on skew | the tile shears on mica, or `calibrate` mis-handles orientation | look at skew against particle orientation; rerun K1's skew rows; tell the project |
| grating start and end differ | thermal drift or creep over the day | report both; the day's scale carries the difference as uncertainty |
| grating large and overlap differ | scanner non-linearity | this is what the overlap is for. Report it; it is a finding about the instrument |
| along-helix scale off by more than 2.4% | the tile's true pitch is not the design's, or the preparation shifted it | a result. K5 tells which |
| marks found in liquid, not in air | drying flattens the hairpins | a result. The kit may be liquid-only |
| too few particles with 3 marks | detection too low, or too few face-up | K2's failure table; more images |
| `afm read` wrong pixel size | channel or export | common-techniques §10 |

## What to hand over

- both folders' `pre/`, committed first
- `during/raw/grating/`, `liquid/`, `air/`, and the bundle folder's `raw/`, untouched
- `during/instrument.json`, `during/scans.csv`, `during/log.md` with the certificate
- `post/` from `calibrate` and `experiment rods`, with the interpretation
- the settings that worked: medium, setpoint, scan size, which K5 fixes as
  its centre point

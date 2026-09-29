# K2 — The calibration tile: does it fold, show its marks, and how much do we get?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 1
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k2-calibration-tile/`
**Run after:** E1 (its magnesium, its reference height, its staple plates) and
E8 (marks visible at all). K1 must have passed before `calibrate` is used on
these images. E11 only for the optional isothermal arm
**Time:** about 3 working days plus 3–5 days for oligo delivery
**Cost:** the marker plate only, about €21.5 per marked cell at list price
(MATERIALS §1). Everything else is E1's
**Read first:** [`common-techniques.md`](common-techniques.md), then
[E1](E1-rectangle-afm.md) and [E8](E8-patterned-rectangle.md). K2 is E8 with a
different pattern and a different question, and it borrows E8's method
step for step. Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md)

---

## What you are testing, and why it matters

The tile is E1's rectangle with hairpins on the staples of a few **isolated
cells**, arranged in a sparse, chiral pattern (the part `calibration-tile`,
being implemented; PROJECT.md describes it). E8 asked whether hairpin marks
can draw a picture. K2 asks what a calibration reference needs on top of that:

1. **Does it fold as well as E1's rectangle?** Same scaffold, same routing,
   a few staples longer. It should. Nobody has checked.
2. **Are the marks found, cell by cell?** E8 reads a picture and tolerates
   up to 3 wrong cells out of 50. A ruler cannot. Each designed mark either
   is found at its cell or is not, and the **mark detection rate** is the
   number that decides whether the tile is a ruler at all.
3. **How much usable tile does one fold give?** Fold yield, purification
   recovery, the well-formed fraction, and the face-up fraction (only
   face-up particles show marks). Their product is what a kit costs per
   calibration. K7's batch size comes from it.

Optionally, K2 also folds the tile **isothermally** at the temperature and
time E11 found. A kit that folds in minutes at one temperature is easier to
make, and is the only kind that could be folded where temperature cannot be
ramped.

## What it decides

- Whether the tile goes forward to K3. It does if it folds, and if enough
  marks are found per face-up particle to fit a scale.
- The yield chain: fold → purification → well-formed → face-up → marks found.
- Whether the isothermal fold is good enough to be the kit's protocol.

## What is predicted

`experiment new` writes the design into `pre/prediction.json`.

| property | predicted | how it will look on the AFM |
|---|---|---|
| outline | as E1: 106.2 × 66.0 nm, about 2 nm tall | as E1, wider by the tip |
| marked cells | as the part: isolated cells, 4 hairpins each | raised spots on face-up particles, nothing on face-down ones |
| centre-to-centre distances | from the part's grid, at design values (PROJECT.md: about 10.5 nm per cell along the helices, 12 nm across) | **not judged in K2**: that is K3, against a grating |
| face-up fraction | **not predicted** | Rothemund: about half |
| mark height above the sheet | **not predicted** | E8 measures it. `calibrate` needs roughly ≥ 1 nm (E8 dry run) |
| fold and purification yield | **not predicted** | measured here |

The across-helix distances depend on a spacing this repository does not know
to better than 13–25% (PROJECT.md). K2 reports them. It does not judge them.

## The gate

Copied into `pre/plan.md` and written there by the experimentalist, with the
supervisor, before the session:

> criterion:

### Proposed, not adopted

> **Fold.** A dominant tile band running like E1-ctrl's in the same gel, with
> a folded-band intensity at least 80% of E1-ctrl's (Fiji, step 5).
> **Count.** At least **100** well-formed tile particles in detail scans, and at
> least **50** of the control.
> **Marks.** Among face-up particles, at least **70%** of designed marked cells
> found at their cells, and marks at undesigned cells in at most **5%** of
> those cells.
> **Control.** At most **5%** of E1's plain rectangles read as marked (E8's
> figure).
> **Isothermal arm (if run).** Informative, not gated: its band as a fraction
> of the ramp fold's, as E11 reports it.
> **Fail.** Marks found on face-up particles at fewer than half their cells:
> the tile cannot carry a ruler as designed. That is a result, and it goes
> back to the design (taller marks), not forward to K3.

Agree the numbers before the session. Report the detection rate per cell
whatever the gate says. A cell that is always missing points to a well.

---

## 0. Create the folder, and order

Do this **after E8 has reported**. If E8 found no marks at all, the tile has
nothing to stand on.

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k2-calibration-tile --part calibration-tile --root experiments
```

**`--part calibration-tile` is being implemented.** When it lands, it is
expected to write, like E8's `--part pattern`:

- `pre/order/calibration-tile_plates.xlsx` and `_bulk.csv`: only the marked
  staples, on plate `marker1`, named `st_hHH_oOOOO_hp`;
- `pre/order/calibration-tile_reuse.json`: the wells of E1's plates to leave
  out of the pool (`omit_from_base`).

Check the files when they appear. If they differ from this, the files are
right and this protocol is out of date. Order the marker plate: standard
desalting, 25 nmol, 100 µM (MATERIALS §1). Supervisor approval first.

Write the gate in `pre/plan.md`, then commit:
`git add experiments/<folder>/pre && git commit -m "K2: pre-register"`

---

## Checklist before you start

- [ ] E1 finished: its magnesium (**M**) and reference flat-sheet height.
- [ ] E8 finished: marks were seen. Its mark height and `blank` fraction noted.
- [ ] K1 passed, or at least the rows for 1 µm, 512-pixel scans and a 10 nm tip.
- [ ] Gate written; `pre/` committed.
- [ ] Marker plate delivered, 100 µM. E1's plates available; E1's pool left
      for the control.
- [ ] Scaffold p7249, 100 nM: at least 35 µL.
- [ ] For the isothermal arm: E11's `post/folding_screen.json` read; best
      temperature **T\*** and shortest good time **t\*** noted; a second
      thermocycler.
- [ ] AFM booked for a long session, liquid imaging if possible; tip
      characteriser.

---

## Day 1 — Pool, fold and check (about 5 hours)

### 1. Make the tile pool (1 h)

Exactly E8's step 1, with the tile's files (MATERIALS §1, *Pooling the
tile*): 5 µL from every well of E1's plates **except** the wells in
`calibration-tile_reuse.json` → `omit_from_base`, plus 5 µL from every well
of the marker plate. That makes 220 staples, **455 nM each**. Print the omit
list and tick it off:

```bash
python -c "import json; [print(o['plate'], o['well'], o['staple']) for o in json.load(open('experiments/<folder>/pre/order/calibration-tile_reuse.json'))['omit_from_base']]"
```

Label: *K2 tile pool, 220 staples, 455 nM each, date*.

### 2. Fold at E1's magnesium (30 min)

Tubes: **tile-a, tile-b, tile-c** (ramp) and **E1-ctrl** (ramp, E1's pool),
and, if you run the isothermal arm, **iso-a, iso-b**. One base mix for all of
them, plus a spare. That is **N = 5** without the isothermal arm and **N = 7**
with it. On ice:

| component | stock | per reaction | base mix (× N) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 5.0 × N µL |
| scaffold p7249 | 100 nM | 5.0 µL | 5.0 × N µL |
| MgCl₂ | 100 mM | V_Mg = M × 50 / 100 | N × V_Mg |
| water | — | 34.5 − V_Mg | N × (34.5 − V_Mg) |
| **total** | | **44.5 µL** | **44.5 × N µL** |

E8's table (step 2) gives V_Mg and the water for every magnesium in E1's
screen. Put **44.5 µL** in each tube, then add **5.5 µL** of the **tile
pool** to tile-a/b/c and iso-a/b, and **5.5 µL of E1's pool** to E1-ctrl.

**Scaffold-only:** 5.0 µL buffer, 5.0 µL scaffold, V_Mg MgCl₂, water to
50 µL (40.0 − V_Mg).

If your stocks differ, recompute with `V = C_final × V_total / C_stock`
(common-techniques §2) and write the stocks in the log.

### 3. Anneal

- **Ramp tubes** (tile-a/b/c, E1-ctrl, scaffold-only): common-techniques §3,
  all in the **same run**.
- **Isothermal tubes**, in the second cycler: E11's program. **80 °C for 5
  min**, then **T\*** for **t\***, then 4 °C. Record the temperature the block
  reports, not the nominal one.

### 4. Gel (2.5–3 h)

Common-techniques §4. Lanes: ladder · scaffold only · E1-ctrl · tile-a ·
tile-b · tile-c · [iso-a · iso-b] · ladder.

Photograph with an exposure that does not saturate the brightest band (the
imager's saturation display), and save an uncompressed TIFF as
`during/raw/gel-day1.tif` (E11 §6).

**If the tile lanes sit in the well and E1-ctrl does not**, the hairpins are
sticking particles together. Go to *When it fails*.

### 5. Quantify the gel (30 min)

Fiji, exactly as E11 §8: one rectangle on the folded band of **E1-ctrl** (the
reference), the same rectangle on each tile lane's folded band, and one on
empty gel as background. Write `during/gel_quant.csv`:

```
lane,arm,folded_band,reference_band,background
tile-a,ramp,7410,8830,310
...
```

(the numbers show the format only). No command reads this file yet. The
ratios go into the interpretation with the raw values beside them, until
`calibrate report` or another command does.

---

## Day 2 — Purify, deposit, image (about 2 hours plus a long AFM session)

### 6. Purify, and measure the recovery (1.5 h + ≥ 1 h)

Pool tile-a/b/c (150 µL) and purify by PEG (common-techniques §5), into
1× folding buffer at **M**. Purify E1-ctrl separately. Purify the isothermal
tubes separately from the ramp tubes. Never mix arms.

Record **the volume you redissolve in**. The recovery needs it.

### 7. Quantify (10 min)

A260 on the NanoDrop, each purified sample. 1 A260 ≈ 11 nM (common-techniques
§6; the hairpins add a few per cent of mass, inside that conversion's
precision, as in E8). Record the reading and the concentration.

**Recovery** is what came out over what went in:

```
recovery = (C_purified × V_redissolved) / (10 nM × V_folded)
```

with 10 nM the scaffold in the fold and V_folded = 150 µL for the pooled ramp
tubes. It is recovery relative to the scaffold. It includes the fold's own
yield and the purification's losses, and it is the number a kit needs.

### 8. Tip radius, before (20 min)

Common-techniques §8. `tip.measured_radius_before_nm`.

### 9. Deposit (15 min)

Each sample on its **own** fresh mica, 1–2 nM, **in liquid** if your AFM can
(common-techniques §7). E8 explains why: Rothemund saw hairpins in liquid, and
they fade under force. Record which you used.

### 10. Image: detail scans (2–4 h)

As E8's step 9: **1 × 1 µm, 512 pixels (≈ 2.0 nm per pixel)**, gentle
setpoint. Enough for **≥ 100 well-formed** tile particles and **≥ 50**
control, from separate areas. Name them as E8 does, because the analysis
finds them by name:

```
during/raw/pattern-01.<ext>, pattern-02.<ext>, ...   the tile, ramp
during/raw/control-01.<ext>, ...                     E1's plain rectangle
during/raw/iso/pattern-01.<ext>, ...                 the tile, isothermal (own subfolder)
```

The isothermal arm has its own subfolder so it is never pooled with the ramp
arm.

### 11. Tip radius, after (20 min)

`tip.measured_radius_after_nm`.

### 12. Aliquot what is left (20 min)

For K3 and K4: single-use aliquots of **5 µL at about 10 nM** in 1× folding
buffer at M (MATERIALS §7), labelled *K2 tile, batch, date, conc., Mg, FT 0*,
at −20 °C. Record how many in the log. These are K3's samples. They are not
K7's, which gets its own batch.

---

## Day 3 — Analysis (about 1–2 hours)

### 13. Check the files and fill in the record

```bash
uv run dobladillo afm read experiments/<folder>/during/raw/pattern-01.<ext>
```

The pixel size must be ≈ 2.0 nm. In `during/instrument.json`, fill in every
field, the magnesium on the mica, both tip radii, and **E1's reference
height** with where it came from (as E8, step 11):

```json
"reference": {"flat_height_nm": 1.4, "from": "E1 <folder> post/measurements.json median_height_nm"}
```

(1.4 shows the *shape* of the entry. It is not a value to copy.)

### 14. Run the readouts

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo experiment report experiments/<folder> --scan experiments/<folder>/during/raw/pattern-01.<ext> --scan ...
uv run dobladillo experiment pattern experiments/<folder>
uv run dobladillo calibrate lateral experiments/<folder>    # (being implemented)
```

- `experiment report` **with `--scan` for the tile files only.** Without it,
  it pools tile and control (E8's warning). It gives the outline, the
  well-formed fraction and its 95% interval.
- `experiment pattern` gives the `pattern` / `mirrored` / `blank` /
  `not_found` split and each particle's observed cells. It reads the designed
  cells from `pre/prediction.json`, **if the tile part records them as E8's
  does**. Confirm this when the part lands. If it does not, skip this line
  and say so in the log.
- `calibrate lateral` (being implemented): the mark detection rate per
  designed cell, the false-mark rate, the mark height above the sheet, and a
  first scale. **The scale is not K2's result.** One instrument, no grating:
  that is K3.

Run the isothermal arm's files the same way, from `during/raw/iso/`.

### 15. Judge against the gate, and commit

In `post/report.md`, under *Interpretation*: each gate criterion in plain
words; the gel ratios from `gel_quant.csv` with their raw values; the
recovery; the yield chain (fold → recovery → well-formed → face-up → marks
found); the per-cell detection rates; the isothermal comparison if run.
Commit `during/` and `post/`.

---

## What to record

- `during/log.md`: stocks and lots; the pool worksheet with the omitted wells
  ticked; the base mix; cycler programs and the actual isothermal
  temperature; gel lane order; purification method, redissolve volume, A260;
  aliquots made; deposition in liquid or air; imaging order and positions.
- `during/instrument.json`: complete, including both tip radii and E1's
  reference height.
- `during/gel_quant.csv`.

## When it fails

| symptom | likely cause | what to try next, recorded as a deviation |
|---|---|---|
| tile in the well, E1-ctrl fine | hairpins sticking particles together | lower magnesium (M − 2), as E8. If it persists, it is a design question |
| tile band weak against E1-ctrl | a pool error: an omitted well pipetted, or a marker well missed | check the pool worksheet; start the pool again rather than correct it |
| every particle `blank` | marks dried or pressed flat, or a blunt tip | liquid; lower setpoint; sharper tip; pixel ≤ 2.6 nm (E8) |
| face-up particles, one cell always missing | one marker well missing, or an omitted base well pipetted | the per-cell rates point to it; check that well |
| marks found but merged | tip too blunt for the cell spacing | tip radius after; the isolated-cell pattern is meant to prevent this, so report it |
| recovery very low | PEG pellet lost, or a poor fold | the gel says which; try the spin filter (common-techniques §5) and record it |
| isothermal band far below the ramp's | E11's window does not carry over to the marked tile | a result. Record it; the ramp stays the kit's protocol |

**A failure, properly recorded, is a result.**

## What to hand over

- `pre/` (committed before the session), including the gate
- `during/raw/`: gel TIFF; native files `pattern-*`, `control-*`, and `iso/`
- `during/instrument.json`, `during/log.md`, `during/gel_quant.csv`
- `post/` from `experiment report`, `experiment pattern` and `calibrate
  lateral`, with your interpretation
- the aliquots for K3, counted and labelled

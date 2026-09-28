# E8 — The patterned rectangle: can we put a detail where we want it?

**Folder:** create it (step 0)
**Run after:** E1 — you need its magnesium, its reference height, and its staple plates
**Time:** about 3 working days plus 3–5 days for oligo delivery
**Cost:** about €150 of new staples (28 oligos, 1,502 nt, list price); everything else is E1's
**Read first:** [`common-techniques.md`](common-techniques.md), then E1

---

## What you are testing, and why it matters

E1 asks whether our rectangle folds. That tests the *outline*. E8 asks the
next question: **can we control a detail inside the outline?**

Twenty-eight of E1's 220 staples are replaced by the same staples carrying a
small DNA **hairpin** on their 3′ end. A hairpin sticks up out of the sheet, so
on the AFM it shows as a raised spot. The 28 marked staples are chosen so that
the spots draw a letter **F** in one corner of the rectangle:

```
seen from the marked face          the rectangle is 10 × 5 cells;
(helices running left to right)    one cell ≈ 10.5 × 12 nm, 4 hairpins
                                   
 .XXX......                        
 .XX.......                        
 .X........                        
 .X........                        
 ..........                        
```

This is the method Rothemund used for his famous patterned origami (Nature
2006, Fig. 3). The design is ours; the only thing borrowed is the idea.

Why an F: an F is **chiral** — it has no mirror symmetry — and it sits
off-centre. So a particle that shows it also tells you **which way round it
landed** and **which face is up**. Later experiments can use the same mark as
an orientation marker.

### The one thing to understand before imaging: one face only

Every hairpin sticks out of the **same face** of the sheet. That is not a
choice; it is where the staple ends point in this design (the software works
it out from the 3D model and the tests check it). When a particle lands
hairpins-down on the mica, the hairpins are underneath it and **you will not
see them**. Rothemund saw this too: flipped rectangles "image poorly", and
only about half of his patterned rectangles were face-up (42% of 55 for one
pattern).

So **about half your particles will look exactly like E1's rectangles.** That
is expected, and it is useful: those particles are a built-in control. The
analysis calls them `blank` and leaves them out of the main number.

## What is predicted

| property | predicted | how it will look on the AFM |
|---|---|---|
| outline | as E1: 106.2 × 66.0 nm, about 2 nm tall | as E1 |
| pattern | an F of 7 cells, 4 hairpins each | a raised F on face-up particles, nothing on face-down ones |
| which way round | face-up particles read as the F, not its mirror image | see the note on mirrors below |
| fraction showing the F | **not predicted** — it depends on how particles land | Rothemund: 42% (of 55) face-up for one pattern |
| height of a hairpin above the sheet | **not predicted** | the analysis needs roughly ≥ 1 nm to see it (dry run below) |

**The hairpin.** 5′-…staple…-**TT GAGAGATG TTTT CATCTCTC**-3′: a two-base
spacer, an 8 bp stem, a four-T loop. primer3 predicts it folds at 69 °C even at
5 mM MgCl₂ (above the 60 °C start of the anneal, so it has folded before any
staple binds), and that it pairs with nothing else in the fold above 24 °C
(the scaffold, all 220 staples). Two hairpins sticking to each other is
predicted to be less stable than two separate hairpins by about 4 kcal/mol.
These are predictions from nearest-neighbour thermodynamics, not
measurements.

**A note on mirrors.** The analysis assumes the image file shows the sample as
seen from above, with the first row at the top — which is how Gwyddion and the
instrument software display it. If **every** particle comes back `mirrored`,
the likely cause is the file's row order, not the sample: say so in the log
and tell the project. A **mix** of `pattern` and `mirrored` would be a real
finding (hairpins visible through the sheet on face-down particles).

## The gate — a proposal; you write the real one

`pre/plan.md` has an empty gate. Write it **with your supervisor, before the
session**, and commit `pre/`. The project proposes:

> **Fold.** A dominant gel band for E8, running like E1's band in the same gel.
> **Count.** At least **100** well-formed particles read in detail scans of the
> patterned sample, and at least **50** of the control.
> **Pattern.** Among well-formed particles that show any marks, the F (or its
> mirror image) is read in **a majority** — the lower end of the 95% interval
> above 50%. A particle "shows the F" when at most 3 of the 50 cells disagree
> with the F turned or mirrored some way: in practice at least 4 of the 7 F
> cells seen, and few spurious ones.
> **Visible at all.** The F is read on at least **20%** of all well-formed
> patterned particles. (Face-up is about half; 20% leaves room.)
> **Control.** At most **5%** of E1's plain rectangles read as the F.
> **Fail.** Marks seen but not spelling the F, or the control reading as
> patterned.

Agree on the numbers before the session. Report the `pattern` / `mirrored`
split whatever the gate says.

---

## 0. Create the experiment folder, and order

Do this **after E1's day-1 gel shows a fold** — there is no point ordering
before the rectangle is known to fold.

```bash
uv run dobladillo experiment new 2026-MM-DD-patterned-rectangle --part pattern --root experiments
```

Replace the date. This writes, in `pre/order/`:

- `pattern_plates.xlsx` and `pattern_bulk.csv` — **only the 28 marked
  staples**, on a plate called `marker1`, named `st_hHH_oOOOO_hp`. The `_hp`
  keeps them apart from E1's staple of the same position in the fridge.
- `pattern_reuse.json` — **the 28 wells of E1's plates to leave out** when you
  pool (`omit_from_base`), and why.

Order the marker plate: standard desalting, 25 nmol, normalised to **100 µM**,
like E1's. Supervisor approval first — it is a purchase.

Then write the gate in `pre/plan.md` and commit `pre/`:
`git add experiments/2026-MM-DD-patterned-rectangle/pre && git commit -m "E8: pre-register"`

---

## Checklist before you start

- [ ] E1 is finished: you have its **magnesium** (call it **M**) and its
      **reference flat-sheet height** from its `post/report.md`.
- [ ] The gate is written and `pre/` is committed.
- [ ] Marker plate delivered, 100 µM.
- [ ] E1's staple plates available (E1's pool took 5 µL per well; E8 takes 5 µL more).
- [ ] Some of **E1's staple pool** left, for the control fold.
- [ ] Scaffold p7249 in stock, concentration known.
- [ ] AFM booked for a longer session than E1 (detail scans take time), with a
      tip characteriser. Liquid imaging if your AFM can.

---

## Day 1 — Pool, fold and check (about 5 hours)

### 1. Make the E8 staple pool (1 h)

**Not E1's pool.** E1's pool contains the plain version of each of the 28
staples that E8 replaces, and plain and marked versions would compete for
the same place on the scaffold. So E8's pool is made from E1's **plates**:

- **5 µL from every well of E1's three plates, EXCEPT the 28 wells** listed
  in `pre/order/pattern_reuse.json` under `omit_from_base`. Print the list and
  tick wells off as you go:

  ```bash
  python -c "import json; [print(o['plate'], o['well'], o['staple']) for o in json.load(open('experiments/2026-MM-DD-patterned-rectangle/pre/order/pattern_reuse.json'))['omit_from_base']]"
  ```

- **5 µL from every well of the marker plate** (28 wells).

That is 192 + 28 = **220 staples**, the same number as E1, so each staple is
at the same concentration as in E1's pool:

```
C_each_in_pool = C_well / N_staples = 100 µM / 220 = 455 nM
```

Total volume 220 × 5 µL = 1,100 µL. Mix, spin down, label "E8 pool, 220
staples, 455 nM each, date".

> **The tip-box trick (Rothemund, Supp. Fig. S50).** With a multichannel
> pipette: take a full tip box, move the tips at the 28 omitted positions into
> an empty box. The first box now picks up only the wells to use from E1's
> plates. It is the easiest way not to pipette a wrong well.

**If you pipette one of the 28 omitted wells by mistake**, the plain and
marked staples compete at that position and that cell will be weak. Start the
pool again; do not "correct" it.

### 2. Fold at E1's magnesium (30 min)

E8 has E1's exact routing; only 28 staples carry a hairpin. So fold at **M**
only, E8 in duplicate, plus **E1's rectangle as the control** — the sample
you will image next to E8 — from E1's pool, from the **same base mix**.

Base mix (4 reactions: 3 plus one spare), on ice:

| component | stock | per reaction | base mix (×4) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 20.0 µL |
| scaffold p7249 | 100 nM | 5.0 µL | 20.0 µL |
| MgCl₂ | 100 mM | V_Mg | 4 × V_Mg |
| water | — | 34.5 − V_Mg | 4 × (34.5 − V_Mg) |
| **total** | | **44.5 µL** | **178.0 µL** |

where every volume is `V = C_final × V_total / C_stock` (common-techniques §2)
with V_total = 50 µL:

- buffer 1× from 10×: 1 × 50 / 10 = **5.0 µL**
- scaffold 10 nM from 100 nM: 10 × 50 / 100 = **5.0 µL**
- staples 50 nM each from 455 nM: 50 × 50 / 455 = **5.5 µL** (added per tube, below)
- MgCl₂ M mM from 100 mM: **V_Mg = M × 50 / 100**
- water: 50 − 5.0 − 5.0 − 5.5 − V_Mg = **34.5 − V_Mg**

| E1's M | V_Mg | water per reaction | MgCl₂ in base mix | water in base mix |
|---:|---:|---:|---:|---:|
| 5 mM | 2.5 µL | 32.0 µL | 10.0 µL | 128.0 µL |
| 7 mM | 3.5 µL | 31.0 µL | 14.0 µL | 124.0 µL |
| 9 mM | 4.5 µL | 30.0 µL | 18.0 µL | 120.0 µL |
| 11 mM | 5.5 µL | 29.0 µL | 22.0 µL | 116.0 µL |
| 13 mM | 6.5 µL | 28.0 µL | 26.0 µL | 112.0 µL |
| 15 mM | 7.5 µL | 27.0 µL | 30.0 µL | 108.0 µL |
| 17 mM | 8.5 µL | 26.0 µL | 34.0 µL | 104.0 µL |
| 19 mM | 9.5 µL | 25.0 µL | 38.0 µL | 100.0 µL |
| 20 mM | 10.0 µL | 24.5 µL | 40.0 µL | 98.0 µL |

Put **44.5 µL** of base mix into three tubes, then add:

| tube | add | total |
|---|---|---:|
| E8-a | 5.5 µL **E8 pool** | 50 µL |
| E8-b | 5.5 µL **E8 pool** | 50 µL |
| E1-ctrl | 5.5 µL **E1 pool** | 50 µL |

And a **scaffold-only** tube: 5.0 µL buffer, 5.0 µL scaffold, V_Mg of MgCl₂,
water to 50 µL (40.0 − V_Mg).

If your stocks differ from these, recompute with the formula and write the
stocks in the log.

### 3. Anneal (35 min)

The same program as E1 (common-techniques §3). All four tubes in the **same
run**.

### 4. Gel (2.5–3 hours)

Common-techniques §4. Lanes: ladder · scaffold only · E1-ctrl · E8-a · E8-b ·
ladder. Save the photo to `during/raw/gel-day1.png`.

**What to look for:** E8's band should run like E1's, very slightly slower (28
hairpins add about 4% to the mass). Write in the log whether it does. **If E8
is mostly in the well and E1-ctrl is not**, the hairpins are sticking particles
together — go to *When it fails*.

---

## Day 2 — Purify, deposit, image (about 2 hours plus a long AFM session)

### 5. Purify E8 and the control (1.5 h + ≥ 1 h)

PEG precipitation (common-techniques §5), each sample separately, redissolved
in 1× buffer at **M**. Pool E8-a and E8-b before purifying if both folded; say
so in the log. Purification also removes the excess marked staples, whose
free hairpins would otherwise coat the mica.

### 6. Quantify (10 min)

A260 on the NanoDrop, both samples. 1 A260 ≈ 11 nM for both (common-techniques
§6; the hairpins change the mass by about 4%, well inside that conversion's
precision).

### 7. Tip radius — before (20 min)

Common-techniques §8. Write `tip.measured_radius_before_nm` in
`during/instrument.json`.

### 8. Deposit (15 min)

Each sample on its **own** fresh mica, 1–2 nM, as common-techniques §7.
**Liquid imaging is preferred here**: Rothemund imaged his hairpins in liquid,
and reports that pressing harder makes them "less distinct, sometimes
disappearing entirely". Whether they survive drying on our design is not
known. Record which you used.

### 9. Image — detail scans, both samples, same tip (2–4 h)

The pattern is ~10 nm cells. A 2 × 2 µm overview at 512 pixels (3.9 nm per
pixel) **cannot** resolve it, and the analysis will skip such scans and say so.

| image | size | pixels | pixel | how many |
|---|---|---|---|---|
| **detail** (for the pattern) | 1 × 1 µm | 512 | ≈ 2.0 nm | enough for **≥ 100 well-formed** E8 particles and **≥ 50** control — about 12 E8 images and 6 control |
| overview (optional) | 2 × 2 µm | 512 | 3.9 nm | a few, to find good areas |

The analysis needs a pixel no larger than a quarter of a cell, about 2.6 nm.
Keep the force gentle (low setpoint): hairpins are soft. A 10 nm tip is
enough for 10 nm cells in the dry run below; a blunter one is not tested past
20 nm.

**Name the files by sample**, exactly like this — the analysis finds them by
name:

```
during/raw/pattern-01.spm, pattern-02.spm, ...    the E8 sample
during/raw/control-01.spm, control-02.spm, ...    E1's plain rectangle
```

(any native extension the toolchain reads; `.gsf` exports only for a format it
does not). Write the order you imaged them in, and the scan positions, in the
log.

### 10. Tip radius — after (20 min)

Write `tip.measured_radius_after_nm`.

---

## Day 3 — Analysis (about 1 hour)

### 11. Check the files and fill in the record

```bash
uv run dobladillo afm read experiments/2026-MM-DD-patterned-rectangle/during/raw/pattern-01.spm
```

Pixel size must match what you set (≈ 2.0 nm for a 1 µm, 512-pixel scan).

In `during/instrument.json`, fill in everything, including the magnesium on
the mica, and **add E1's reference height** — the median height of E1's
well-formed rectangles, from E1's `post/report.md` — like this:

```json
"reference": {"flat_height_nm": 1.4, "from": "E1 2026-09-22-rectangle-afm post/measurements.json median_height_nm"}
```

(1.4 is the *shape* of the entry, not a value to copy.) The command refuses
to run without it, and without a measured tip radius — it will not use the
nominal one on the box.

### 12. Run the analysis

```bash
uv run dobladillo experiment check experiments/2026-MM-DD-patterned-rectangle
uv run dobladillo experiment pattern experiments/2026-MM-DD-patterned-rectangle
```

**Do not use `experiment report` on this folder without `--scan`**: it reads
every file in `during/raw/`, and would pool the patterned and control samples
into one population.

`experiment pattern` writes `post/pattern.json` and `post/pattern.md`. For each sample it reports
the particle classes (as E1) and, for every **well-formed** particle, one of:

| verdict | meaning |
|---|---|
| `pattern` | the F, the right way round (either end first) — a face-up particle |
| `mirrored` | the F's mirror image |
| `blank` | no cell stands above the sheet — a face-down particle, or no marks |
| `not_found` | something stands proud, but it is not the F any way round |

with the fractions and 95% intervals the gate needs: `found` (F either way
round, among all well-formed), `found_among_marked` (among non-blank ones),
and the `mirrored` share. Each particle also gets `orientation_deg`, the
direction the F's helices run in the image — the orientation marker for later
experiments.

### 13. Judge against the gate, and commit

In `post/pattern.md`, under *Interpretation* (below the line — everything above
it is regenerated, and what you write below survives a rerun): each gate
criterion, passed or not, in plain words; the `pattern`/`mirrored` split; the
blank fraction (how many landed face-down). Commit `during/` and `post/`.

---

## When it fails

| symptom | likely cause | what to try next — record it as a deviation |
|---|---|---|
| E8 stuck in the well, E1-ctrl fine | hairpins sticking particles together (predicted unlikely, not excluded) | lower magnesium (M − 2); if it persists, Rothemund's "dumbbell" hairpin was designed against exactly this — tell the project, it is a new design |
| E8 and E1-ctrl both fail to fold | not an E8 problem | back to E1 |
| every particle `blank`, control `blank` | hairpins not visible: dried flat, pressed flat, or a blunt tip | image in liquid; lower the setpoint; sharper tip; check the pixel is ≤ 2.6 nm |
| every particle `blank`, gel fine | marked staples missing from the pool | check the pool worksheet: were the marker wells added? |
| many `not_found`, few `pattern` | marks visible but the F is broken: an omitted well pipetted (plain and marked staples compete), drift, or marks too weak | check the pool; smaller, slower scans; look at the `observed` cells in `pattern.json` — a consistently missing cell points at one well |
| everything `mirrored` | the file's rows are stored bottom-up | open one scan in Gwyddion and compare; tell the project. Not a sample failure |
| a mix of `pattern` and `mirrored` | marks visible through face-down sheets, or some particles folded differently | a real result — record it, image more |
| control reads as the F | the analysis sees sheet texture or debris as marks | report it as it is. Do **not** change the analysis thresholds after seeing the data — that is tuning, and it makes the gate meaningless |
| `pattern` far below 20% but not zero | most particles land face-down on your mica | a result about deposition — record it; the fraction among marked particles is still the pattern test |
| scans skipped as "too coarse" | overview scans in `pattern-*` | image 1 µm detail scans; overviews may be named `overview-*` |

**A failure, properly recorded, is a result.**

---

## What to hand over

- `pre/` (committed before the session), including the gate
- `during/raw/`: gel photo, native AFM files named `pattern-*` and `control-*`
- `during/instrument.json` complete: both tip radii, magnesium, and E1's reference height with where it came from
- `during/log.md`: stocks, the pool (which wells were skipped), imaging order and positions, liquid or dry
- `post/pattern.json` and `post/pattern.md` from `dobladillo experiment pattern`, with your interpretation
- the `pattern` / `mirrored` / `blank` split, whatever the gate says

---

## Dry run — done before any order

The whole chain was run on **synthetic** scans with the commands above:
`experiments/protocols/e8_dryrun.py --out <scratch dir> [--realistic]`. It
builds the order, creates a folder, writes 12 detail scans of E8 (half the
particles marks-up, a fifth of marks knocked out at random) and 6 of the
control, fills `instrument.json` with values marked synthetic, and runs
`afm read`, `experiment check`, `experiment pattern` and the proposed gate.

What it showed (seed 0, 10 nm tip, 0.12 nm pixel noise):

| marks | artefacts | E8 read: pattern / mirrored / not_found / blank | control read as F | proposed gate |
|---|---|---|---|---|
| 1.0 nm | none | 72 / 0 / 0 / 72 | 0 of 72 | passes |
| 1.0 nm | bow, drift, streak | 71 / 0 / 0 / 71 | 0 of 71 | passes |
| 2.0 nm | bow, drift, streak | 71 / 0 / 0 / 71 | 0 of 71 | passes |
| 1.0 nm, 15 nm tip, 30% missing | bow, drift, streak | 71 / 0 / 0 / 71 | 0 of 71 | passes |
| 0.7 nm | bow, drift, streak | 12 / 0 / 54 / 76 | 0 of 71 | fails (pattern, visible) |
| 0.5 nm | none | 0 / 0 / 0 / 144 | 0 of 72 | fails (pattern, visible) |

So: **marks need to stand roughly 1 nm above the sheet** for this analysis at
this noise level; below that it reports `blank` or `not_found`, never a
confident wrong answer. How tall our hairpin reads on your instrument is not
known — that is part of what E8 measures. The dry run also found that tall
marks broke particle outlines in the E1 segmentation (half-height at the top
of the marks is the sheet's own height), which is why E8's analysis takes the
outline at the sheet's plateau; and that `experiment check` flags the record
until `pre/` is committed to git — as it should.

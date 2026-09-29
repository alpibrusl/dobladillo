# K1 — Does `calibrate` recover what we put in, and say how sure it is?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 0
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k1-software-validation/`
**Run after:** nothing at the bench. It needs `dobladillo calibrate` and the
`calibration-tile` part, both in place since 2026-09-29
**Time:** about 1 day once the commands exist, most of it waiting for runs
**Cost:** none. No oligos, no instrument time
**Read first:** `experiments/AGENTS.md`, the E8 dry run (end of
[E8](E8-patterned-rectangle.md)), and [PROJECT.md](../../projects/afm-calibration-kit/PROJECT.md)

---

## What you are testing, and why it matters

Every later K experiment reads its result through `dobladillo calibrate`.
A calibration routine that is subtly wrong does not look wrong. It returns a
scale factor of 1.013 where the truth is 1.030, with an uncertainty of
±0.002, and every instrument calibrated with it inherits the error with
confidence. Nothing downstream can tell.

So the software is tested first, on images whose answer is known because we
put it there, and before it ever sees a real scan. E1–E4 and E8–E10 were each
walked through on synthetic data before any order. K1 does the same for
calibration, and goes further in one respect. The question is not only
whether the value comes out right, but **whether the stated uncertainty is
honest**.

## What it decides

- Whether `calibrate lateral`, `tip` and `drift` may be used on K2–K7's
  real images, and over what range of conditions (pixel size, tip radius,
  mark height, noise).
- Which conditions it must refuse. A refusal with a named reason is a pass
  there; a number is a fail.
- Whether its tip reconstruction agrees with an independent implementation
  (Gwyddion's blind estimation) on the same images.

## What "validated" means here

Six properties, each measured, none assumed. The thresholds are proposals
(see the gate).

| property | what is measured | on what |
|---|---|---|
| **accuracy** | recovered minus injected: scale X, scale Y, skew, tip apex radius and shape, drift velocity | synthetic images of known content |
| **coverage** | the fraction of seeds whose stated 95% interval contains the injected value | the same, many seeds per condition |
| **refusal** | a named refusal, not a number, when the input cannot support one | negative controls (below) |
| **independence** | agreement with a method we did not write | Gwyddion's blind tip estimation, on the same images |
| **robustness** | accuracy and coverage with realistic artefacts on | bow, drift shear, a tip-change streak (`afm synthetic --realistic`'s set), missing marks, face-down particles |
| **reproducibility** | the same seeds give the same numbers | pinned in `tests/`, as every design script's outputs are |

**Coverage is the one people skip.** An interval that holds the truth in 60%
of seeds is not a 95% interval, whatever it is labelled. The proposed
threshold allows for the finite number of seeds. With 100 seeds, an interval
whose true coverage is 95% gives 90 or more hits 99% of the time. One whose
true coverage is 85% gets there only 10% of the time.

## What is predicted

The injected values are the prediction. They are chosen, written into
`pre/` and committed **before** any run on the validation seeds (step 1).

### What the synthetic generator must be able to do

Checked on 2026-09-29. Today's generators (`afm synthetic`,
`imaging.synthetic_pattern.patterned_scan`, used by `e8_dryrun.py`) place
particles and marks, model a **spherical** tip of a given radius, and add
scanner bow, drift shear and a streak. K1 also needs:

- an **injected lateral distortion**: scale X ≠ scale Y, and skew;
- an **arbitrary tip shape**, not only a sphere: at least an asymmetric
  apex, and a tip that blunts between images (wear);
- **drift over time**, as a displacement per frame, for `calibrate drift`;
- the **calibration tile**'s pattern, at random orientations and landing
  face-up or face-down.

Not all of these exist yet (the calibrate commands take scan files; there
is no folder-level `calibrate report`). If any is missing
when K1 runs, the dependent row of the grid below cannot run. Say so in
`post/`. Do not substitute a different test.

### The condition grid (a proposal)

| factor | levels | why these |
|---|---|---|
| scale X, scale Y | −3%, 0, +3%, independently | the size of error a scanner calibration commonly leaves, and of the literature's 3–10% preparation spread |
| skew | 0°, 0.5°, 1.5° | small enough to be missed by eye |
| tip | spherical 5, 10, 15, 20 nm; one asymmetric; one that blunts from 10 to 15 nm over the session | common-techniques §8: a nominal 10 nm tip is 8–20 nm in use |
| mark height above the sheet | 0.7, 1.0, 2.0 nm | the E8 dry run: reliable at 1 nm, failing at 0.7 |
| pixel | 1.0, 2.0, 2.6 nm | 2.6 nm is the coarsest E8's analysis accepts |
| noise | 0.12 nm (E8's dry run), 0.25 nm | |
| artefacts | off; bow + drift shear + streak | |
| face-up fraction | 50% | Rothemund's rectangles, about half face-up |
| missing marks | 0%, 30% | the E8 dry run's 30% row |

Not every combination is needed. The proposal is: every factor at every level
with the others at their central value, **plus** the full crossing of scale ×
skew × tip, at 100 seeds each.

### Negative controls: each must be refused, with its reason

- an image of E1's plain rectangle declared as the tile (no marks);
- the tile with 90% of marks missing;
- a pixel of 4 nm (E1's 2 µm overview);
- a scan with no declared reference;
- a reference declared with a geometry that contradicts the image (the
  GATTA-AFM's nominal 90 × 70 nm against the tile);
- fewer particles than `calibrate`'s own minimum.

---

## 0. Create the folder

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k1-software-validation --part calibration-tile --root experiments
```

**`--part calibration-tile` exists (2026-09-29).** Before it did, this
command refuses with `unknown_part`, which is correct. The folder gets an
order file. **Do not order it.** K1 is software.

## 1. Write the plan and the gate, and commit `pre/`

In `pre/plan.md`, write:

- the condition grid you will run (start from the proposal above);
- the **development seeds** (0–99, say), on which the implementers may tune;
- the **validation seeds** (1000–1099, say), which nobody runs until `pre/` is
  committed;
- the gate.

```bash
git add experiments/<folder>/pre && git commit -m "K1: pre-register"
```

**Why the split matters.** A threshold adjusted after seeing the validation
seeds is the software equivalent of a gate written after the data. E8's
failure table says the same about its thresholds.

## 2. Run the synthetic grid (hours)

With the commands as they land. The arguments here are the shape this
protocol assumes. The commands' own `--help` wins.

```bash
uv run dobladillo calibrate lateral <scans...> --json
uv run dobladillo calibrate tip <scan> --json
uv run dobladillo calibrate drift <frames...> --interval-s <s> --json
uv run dobladillo calibrate report experiments/<folder>   # NOT BUILT YET: the folder-level report; until then the three JSON files above are the record
```

**Synthetic scans are regenerated from their seeds. They are not committed,
and never go in `during/raw/`**, which holds only files an instrument wrote.
Record the generator's version and every seed in `during/log.md`.

## 3. Independent check: Gwyddion (1–2 h)

For 20 synthetic images covering the tip levels, run Gwyddion's *Data Process
→ SPM Modes → Tip → Blind Estimation* (common-techniques §8). Record the
apex radius it gives, and the settings you used, in
`during/gwyddion_tip.csv`:

```
image,seed,injected_tip,gwyddion_radius_nm,gwyddion_settings
```

## 4. Public data (a few hours, once its licence is checked)

**Zenodo record 15370091** (Rabbe & Keller 2025): AFM images of
streptavidin-decorated DNA origami.

1. **Check the licence first**, on the record itself, and write it in
   `during/log.md` with the date. If it does not permit this use, or copying
   into a private repository, **stop this step** and record why. Downloading
   the files is a download: the person running K1 decides it.
2. Record the DOI, every file name and its SHA-256 in `during/log.md`. If the
   licence allows copying, put the files in `during/raw/public/` untouched.
   Otherwise keep them outside the repository and record where.
3. `uv run dobladillo afm read <file>` on each: did the pixel size and height
   units come through (common-techniques §10)?
4. There is no ground truth here. What is tested:
   - **consistency**: images from one session give the same scale and skew
     within their intervals;
   - **declared geometry**: the reference geometry must come from the
     publication, written into the declaration with its source. If the
     publication does not state it, record that and use the images for
     consistency only;
   - **refusal**: where `calibrate` cannot read a reference it must say so,
     not guess.

Other public datasets can be added the same way, each with its licence
checked and recorded first.

---

## What to record

- `pre/plan.md`: the grid, the seed split, the gate. Committed first.
- `during/log.md`: software version (`dobladillo version`) and commit hash;
  generator version; every seed; the public dataset's DOI, licence, date
  checked, file names and hashes; anything that crashed.
- `during/gwyddion_tip.csv`: the independent check.
- `post/`: the `--json` output of each `calibrate` command (`lateral.json`, `tip.json`, `drift.json`); a folder-level `calibrate report` is not built yet. Accuracy and
  coverage per quantity and condition, every refusal with its kind, and the
  Gwyddion comparison. Nothing in `post/` is edited by hand.

## The gate

Copied into `pre/plan.md`, and filled there by the maintainer or the
experimentalist, before step 2:

> criterion:

### Proposed, not adopted

> **Accuracy.** At the central condition (10 nm tip, 1 nm marks, 2 nm pixel,
> 0.12 nm noise, artefacts on), the median error on scale X and Y is below
> 0.5% and on skew below 0.2°.
> **Coverage.** For every quantity and condition in the grid, at least 90 of
> 100 validation seeds have the injected value inside the stated 95%
> interval.
> **Refusal.** Every negative control is refused with a named reason. Any
> number returned for one is a fail, however plausible.
> **Tip.** Apex radius within the stated uncertainty of the injected one for
> spherical tips of 5–20 nm, and within the stated uncertainty of Gwyddion's
> estimate on the same images. A systematic difference from Gwyddion is
> reported, not fixed after the fact.
> **Where it stops.** The conditions at which accuracy or coverage fail are
> reported as the software's limits. They are not a failure of K1.

---

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| accurate, but coverage well below 95% | uncertainty ignores a source: the tip, the mark-detection threshold, or particle-to-particle scatter | report it; the fix is in the software, and is tested on development seeds only |
| scale X and Y biased the same way | pixel size read wrongly, or the design pitch is wrong | `afm read` on the synthetic file; check the declared geometry against the part |
| skew recovered only at some orientations | the fit does not use the spread of landing angles | report it (see PROJECT.md: anisotropy and skew are separable from the object only across orientations) |
| tip radius systematically above truth | blind reconstruction gives an outer bound **[literature]**, sharpest where features are sharpest | expected to some degree; state the bias, do not subtract it |
| Gwyddion and `calibrate` disagree | different settings, or one is wrong | record both settings; run both on the same simple test object |
| a negative control returns a number | the refusal is missing | a fail. Report it |
| public data licence unclear | — | stop that step; do not use it |

## What to hand over

- `pre/` committed before any validation seed was run
- `during/log.md`, `during/gwyddion_tip.csv`, and the public data record
- `post/` from `calibrate report`, with the interpretation below its line
- the list of conditions under which `calibrate` may be used on real images,
  which K2–K7 cite

# K7 — Kit format and shelf life: which form keeps, and for how long?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 4
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k7-shelf-life/`, one
folder for the whole series
**Run after:** K2 (a fold, and its recovery, which sizes the batch), K3 (the
imaging settings and grating routine), K5 (the spread at the centre point,
which says what change is detectable)
**Time:** 12 months elapsed. One bench day at the start, then about one AFM day
per time point (six)
**Cost:** no new oligos. About 60 mica discs, tips, freezer space
**Read first:** [K2](K2-calibration-tile-fold.md), [K3](K3-lateral-calibration.md),
[K5](K5-preparation-sensitivity.md). Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md) §7

---

## What you are testing, and why it matters

A kit is something that sits in a freezer or a drawer until someone needs it.
Whether the tile is still the tile after a month at −20 °C, after being thawed
three times by a careless user, or after a year dried on mica is not a detail.
It decides what the kit *is*: a tube, a disc, or a protocol plus a fresh fold.

Korpelainen et al. report their dry origami tile stable for at least 12 months.
Nobody has measured ours, in any form, and the hairpin marks are a new thing
to lose.

## What it decides

- Which formats the kit offers, and the shelf life stated for each.
- How many freeze-thaw cycles the kit label allows.
- Whether dried-on-mica works for the tile at all. It needs marks that survive
  drying (K3's air arm).

## The formats

| code | format | storage | what is tested |
|---|---|---|---|
| F-20 | frozen aliquots, single use | −20 °C | the default kit format |
| F-80 | frozen aliquots, single use | −80 °C | optional; whether colder helps |
| F4 | liquid aliquots | 4 °C | a user who keeps it in the fridge |
| FT | frozen aliquots, thawed and refrozen **n** times | −20 °C | n = 1, 3, 5, 10, all at t0 |
| DRY | deposited and dried on mica at t0 | desiccator, room temperature, closed box | the Korpelainen et al. format |

Every aliquot is **5 µL at about 10 nM** in 1× folding buffer at E1's
magnesium (MATERIALS §7). All come from **one batch**, named in the log.

**Time points:** t0 (day of the batch), 1 week, 1 month, 3 months, 6 months,
12 months. **Two** aliquots, or two discs, per format per time point.

That is 3 liquid formats × 6 time points × 2 = 36 aliquots, 8 for the
freeze-thaw series (4 values of n × 2), and a few to make the 12 DRY discs at
t0: **about 48 aliquots**. MATERIALS §7 sizes the fold from this and K2's
recovery.

### What is measured at every time point

The same things, on the same instrument, with the same routine:

- **well-formed fraction** (the outline survives);
- **mark detection rate** among face-up particles (the marks survive);
- **the tile's along- and across-helix pitch as a ratio to the grating's**
  at the overlap size (K3). The ratio, not the raw scale: the instrument may
  be serviced or recalibrated within a year, and the grating carries that
  change out;
- for the liquid formats, a **gel** lane per format (fragments and smear show
  there before they show on mica).

**A change counts only if it exceeds K5's spread at the centre point.** A
drift smaller than that is invisible to anyone using the kit, and reporting
it as a change would be reading noise.

## What is predicted

Nothing is predicted for our tile. Korpelainen et al.'s 12 months dry is the
published point of comparison, for a different tile without hairpin marks.

## The gate

Copied into `pre/plan.md` and written there by the experimentalist before the
batch is folded:

> criterion:

### Proposed, not adopted

> **Shelf life, per format:** the last time point at which well-formed
> fraction, mark detection rate and both pitch ratios are all within K5's 95%
> spread of t0.
> **Kit format:** at least one liquid format keeps all four to **6 months**,
> and DRY to **12 months** if it keeps marks at t0 at all.
> **Freeze-thaw:** the largest n at which all four are within K5's spread;
> the label allows one fewer.
> **Fail (of a format, not of K7).** A format that changes beyond the spread
> by 1 week is not offered.

---

## 0. Create the folder, and fold the batch (bench day)

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k7-shelf-life --part calibration-tile --root experiments
```

Write the gate, the time
points as calendar dates, and the batch name in `pre/plan.md`. Commit `pre/`
**before** folding.

Then fold **one batch of 10 reactions**, or as many as K2's recovery says are
needed for about 48 aliquots (MATERIALS §7). Use K2's steps 2–7: the base mix
for N = 11, the tile pool, the anneal, a gel, PEG purification into 1×
folding buffer at M, A260. Dilute to 10 nM, and aliquot 5 µL into
low-binding tubes, labelled *K7, batch, format, time point, replicate*.

- **F-20, F-80, FT**: freeze at once.
- **F4**: into the fridge.
- **DRY**: 12 discs today. Deposit per K5's centre point, dry variant
  (common-techniques §7, air), and store each in a closed box in the
  desiccator. Label the box, not the mica.
- **FT**: thaw on ice, then refreeze, n times, with at least 30 minutes frozen
  between thaws. Keep a tally on the tube.

## At each time point (about one AFM day)

1. Take the two aliquots or discs per format for that time point. Thaw frozen
   aliquots **on ice**. Record the date and the time since t0.
2. **Gel** (liquid formats): common-techniques §4, one lane per format and
   replicate, plus a scaffold-only lane. `during/raw/<tp>/gel.tif`.
3. **Grating, start**: K3 step 1, overlap scans. `during/raw/<tp>/grating/`.
4. **Tip, before**: common-techniques §8.
5. For each liquid format: deposit per K5's centre point, liquid. Image as K5
   (at least **50** face-up particles with marks, plus 2 overlap scans).
   `during/raw/<tp>/<format>/`.
6. For DRY: image the disc dry, as K3's air arm. Optionally, add imaging
   buffer and image it again in liquid, as a *rehydrated* arm, in its own
   subfolder. Do marks come back?
7. **Tip, after**, and **grating, end**.

`<tp>` is `t0`, `w1`, `m1`, `m3`, `m6`, `m12`.

The t0 time point runs on the batch day or the day after. It is the baseline
everything else is compared with, so do not skip it.

## What to record

- `during/scans.csv`, as K3's, with columns for the time point and format.
- `during/storage.csv`, one row per aliquot or disc: code, format, date made,
  date used, freezer, freeze-thaw count, anything that happened to it (a
  freezer alarm, a power cut). **A freezer event is data.** Write it the day
  it happens, not at the next time point.
- `during/log.md`: per time point, the date, tip, grating result, room
  temperature, anything unusual.
- `during/instrument.json`: as common-techniques §10; later time points' tip
  radii go in `scans.csv` and the log.

The CSV formats are this protocol's proposal. `calibrate`'s own wins when it
lands.

## Readout

After each time point:

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate lateral experiments/<folder>/during/raw/tile-*.gsf --json > experiments/<folder>/post/lateral.json
uv run dobladillo experiment report experiments/<folder> --scan experiments/<folder>/during/raw/<tp>/<format>/pattern-01.<ext> --scan ...
```

After 12 months, or whenever a format fails:

```bash
uv run dobladillo calibrate report experiments/<folder>   # NOT BUILT YET: the folder-level report; until then the three JSON files above are the record
```

It reports, per format, the four quantities against time relative to t0,
with K5's spread drawn in. `experiment report` gives the well-formed fraction
per format and time point, one `--scan` set at a time, so formats are never
pooled.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| F4 fragments within weeks | nucleases, or slow unfolding at 4 °C | a result. Check the technique (common-techniques §0) on the next batch before concluding |
| FT loses marks before outline | the hairpins unfold or the staples exchange | a result about the marks |
| DRY has no marks at t0 | drying flattens them (K3's air arm said so?) | the DRY format is outline-only; say so, and keep its time series for the outline |
| every format jumps at one time point | the instrument, not the sample | the grating ratio should absorb it. If it does not, the tip or the day; that is why t0's routine repeats |
| a freezer failure | — | record it in `storage.csv`; the affected aliquots are reported apart, not discarded silently |

## What to hand over

- `pre/` committed before the batch
- `during/raw/<tp>/…` for every time point, untouched
- `during/scans.csv`, `during/storage.csv`, `during/log.md`
- `post/` from `calibrate report`, with the interpretation: the shelf life per
  format and the freeze-thaw limit, which the kit's label states

# K4 — The tip: do the tile and the bundle reconstruct the same tip as the staircase?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 2
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k4-tip/`
**Run after:** K1 (the tip rows passed), K2 (tile aliquots), E10 (the bundle
folds straight). Without E10, run the tile against the staircase alone and
say so
**Time:** one long AFM session (6–8 h, one tip throughout) plus half a day of analysis
**Cost:** GATTA-AFM 3D, EUR 450 (list, 2026-09-29); GATTA-AFM, EUR 350, optional
**Read first:** [`common-techniques.md`](common-techniques.md) §8, [K2](K2-calibration-tile-fold.md),
[E10](E10-six-helix-bundle.md), and the GATTA-AFM 3D product sheet.
Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md) §5–§6

---

## What you are testing, and why it matters

Every dimension in this project is corrected for the tip: 8.7 nm off a 36 nm
width for a 10 nm tip on a 2 nm sheet (`experiments/README.md`). So far the
tip is a single number, a radius, estimated in Gwyddion from a tip-check
sample. K4 asks whether **our own samples** can reconstruct the tip. It checks
this against a sample built for exactly that job: GATTAquant's GATTA-AFM 3D,
a DNA-origami staircase of about 2.5, 5, 12.5 and 20 nm steps (Kolbeck et al.,
*Nano Lett.* 23, 1236, 2023).

**Blind reconstruction** (Villarrubia 1997 **[literature]**) finds the
bluntest tip consistent with an image, with no knowledge of the sample. Two
properties matter here:

- the result is an **outer bound**: the real tip is at least as sharp.
  Sharper sample features give a tighter bound;
- it characterises the tip **only as deep as the tallest feature imaged**.
  The tile is a 2 nm sheet with marks on it, so it sees the last 2–3 nm of the
  apex. The bundle is taller (8 nm designed, less when dry). The staircase
  reaches about 20 nm. That depth is why the staircase exists.

So the honest comparison is **depth by depth**: in the range both references
probe, do they bound the same tip? Above the tile's depth, only the bundle and
the staircase have anything to say. K4 does not expect the tile to replace
the staircase. It asks what the tile covers, and whether it covers that
correctly.

The same session measures **tip wear**. The staircase is imaged at the start,
middle and end, so a tip that blunts is seen blunting, not mistaken for a
difference between samples.

## What it decides

- Whether the kit's tile can report the tip apex, and to what depth.
- Whether the bundle extends that depth usefully.
- How fast a tip wears on these samples in these conditions. That sets how
  often K5–K7 must re-measure it.
- Whether `calibrate tip` agrees with Gwyddion's blind estimation on real
  images, not only on K1's synthetic ones.

## What is predicted

Nothing about the tip itself: that is what is measured. What is expected:

| comparison | expected |
|---|---|
| tile against staircase, depth ≤ the tile's height | the same apex within uncertainty, or the tile's bound blunter (its features are less sharp) |
| bundle against staircase, depth ≤ the bundle's height | the same, to a greater depth |
| staircase start / middle / end | the same, or monotonically blunter (wear) |
| `calibrate tip` against Gwyddion, same image | the same within uncertainty (K1 tested this on synthetic images) |

## The gate

Copied into `pre/plan.md` and written there by the experimentalist before the
session:

> criterion:

### Proposed, not adopted

> **Agreement.** In the depth range the tile probes, its reconstructed apex
> radius agrees with the staircase blocks immediately before and after it,
> within their combined 95% uncertainty. The same for the bundle, over its
> depth.
> **Wear.** The apex radius from the first and last staircase blocks either
> differs by more than the combined uncertainty (wear resolved, and its rate
> reported) or does not (wear bounded, and the bound reported).
> **Independence.** `calibrate tip` and Gwyddion agree on the staircase images
> within uncertainty.
> **Fail.** The tile and the staircase disagree beyond uncertainty in their
> common depth range, and the difference is not bracketed by wear. Either the
> software or the tile's usefulness for tips is in question.

---

## 0. Create the folder

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k4-tip --part calibration-tile --root experiments
```

(`--part calibration-tile` is being implemented.) Do not order: K4 uses K2's
aliquots and E10's bundle.

**Choose the medium** before committing `pre/`. The staircase is used under
its supplier's conditions. If its product sheet supports liquid, use liquid,
the tile's target. If it supports only dry, run **everything dry**. One tip
in one medium is the point, and a tip moved between air and liquid is not the
same tip. Write the choice in `pre/plan.md`.

## Checklist before you start

- [ ] K1's tip rows passed.
- [ ] GATTA-AFM 3D in hand, product sheet read: in solution or on a substrate,
      storage, deposition, imaging conditions.
- [ ] K2 aliquots (2) and purified bundle (E10 recipe), or a fresh E10 fold.
- [ ] One tip, and spares from the **same lot** (MATERIALS §5).
- [ ] Your instrument can change samples **without changing the tip**. If it
      cannot in liquid, run dry and record why.
- [ ] Gate written; `pre/` committed.

---

## The session (6–8 h, one tip)

### 1. Prepare the three samples (30 min)

Each on its **own** mica, just before the session:

- **staircase (S):** exactly per its supplier's protocol, not ours;
- **tile (T):** one K2 aliquot, common-techniques §7, in the chosen medium;
- **bundle (B):** E10's deposition (step 10), or its liquid equivalent,
  recorded as a deviation from E10's source if you image in liquid.

### 2. Image in blocks, in this order

| block | sample | images | size | pixels |
|---|---|---|---|---|
| S1 | staircase | 3 | as the supplier recommends to include all four steps | 512 |
| T1 | tile | 4 | 1 × 1 µm | 512 |
| B1 | bundle | 2 | 2 × 2 µm | 1024 |
| S2 | staircase | 3 | as S1 | 512 |
| T2 | tile | 4 | 1 × 1 µm | 512 |
| B2 | bundle | 2 | 2 × 2 µm | 1024 |
| S3 | staircase | 3 | as S1 | 512 |

Same setpoint, gain and scan rate for every block. Every tile and bundle block
sits between two staircase blocks, so any wear is bracketed. Optional: a
GATTA-AFM (rectangle) block after T2, per its supplier's protocol.

Files to `during/raw/`, one subfolder per sample so nothing is pooled:

```
during/raw/staircase/S1-01.<ext>, S1-02 ...
during/raw/tile/T1-01.<ext>, ...
during/raw/bundle/B1-01.<ext>, ...
```

**Do not stop to look at reconstructions during the session.** The order and
the settings are the experiment. Changing either mid-session because a number
looked odd is how wear gets confused with a sample difference.

### 3. Before and after radius (the established routine)

Common-techniques §8 still applies. Estimate the radius in Gwyddion from **S1**
(before) and **S3** (after), and write them into `during/instrument.json` as
`tip.measured_radius_before_nm` and `_after_nm`, with the tip's part number and
nominal radius. This is independent of `calibrate`, and it is what every other
command reads.

---

## What to record

`during/sequence.csv`, one row per image:

```
block,sample,file,start,end,lines,scan_size_nm,setpoint,rate_hz,medium
S1,staircase,staircase/S1-01.spm,09:12,09:21,512,1000,...,1.0,liquid
...
```

(the rows show the format only). **Lines scanned** and **time** are what wear
is plotted against. The format is this protocol's proposal. `calibrate`'s own,
when it lands, wins.

`during/gwyddion_tip.csv`: Gwyddion's blind estimate for every staircase image
and at least two images per tile and bundle block, with the settings used.

`during/log.md`: the staircase's lot and product sheet version; how samples
were exchanged; any tip crash, jump or contamination event, with the time.
A contamination event splits the session: say which blocks are before it.

## Readout

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate tip experiments/<folder>      # (being implemented)
uv run dobladillo calibrate report experiments/<folder>   # (being implemented)
```

What K4 needs from `calibrate tip` (being implemented), per block: the
reconstructed tip, its apex radius with uncertainty, and **the depth to which
it is determined**. From `calibrate report`: apex radius against cumulative
lines scanned; tile and bundle against the bracketing staircase blocks,
depth by depth; the Gwyddion comparison. Nothing in `post/` is edited by
hand.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| a sudden change between blocks | tip contamination or a crash | the log's time says which blocks are before it; split the analysis there. Do not average across it |
| tile's apex bound much blunter than the staircase's | the tile's features are not sharp enough to bound this tip | a result about the tile's reach; report the depth it does cover |
| tile's bound sharper than the staircase's | the staircase's edges are rounder than the tile's at the apex, or noise | not a contradiction in itself: both are outer bounds. Check the noise threshold in both methods |
| staircase blocks disagree with no trend | reconstruction noise; too few images | more images per block next time; report the scatter as uncertainty |
| Gwyddion and `calibrate` disagree on the staircase | settings, or a fault | record both settings; compare on K1's synthetic images again |
| the staircase is not imaged as the supplier describes | a different medium or a damaged sample | follow the supplier's protocol; record the lot. Whether to raise it with the supplier is the maintainer's decision |

## What to hand over

- `pre/` committed before the session, with the medium chosen
- `during/raw/staircase/`, `tile/`, `bundle/`, untouched
- `during/instrument.json` (radii from S1 and S3), `during/sequence.csv`,
  `during/gwyddion_tip.csv`, `during/log.md`
- `post/` from `calibrate`, with the interpretation: the depth each reference
  covers, the agreement in the common range, and the wear rate or its bound
